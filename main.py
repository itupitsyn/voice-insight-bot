import whisperx
from dotenv import load_dotenv
import os
import requests

import markdown  # pip install markdown
from bs4 import BeautifulSoup  # pip install beautifulsoup4

import telebot

import threading
import queue

from localization import get_localized, get_language_code

from message_handlers import add_handlers, get_base_markup

device = "cuda"
compute_type = "float16"

print("Start loading model")
# 1. Transcribe with original whisper (batched)
model = whisperx.load_model("large-v2", device, compute_type=compute_type)

# save model to local path (optional)
# model_dir = "/path/"
# model = whisperx.load_model("large-v2", device, compute_type=compute_type, download_root=model_dir)

summary_prompt = f'''Шаблон для создания summary:
Тема обсуждения: <text>

- Задача: <text>
- Описание / Концепция / Детали задачи: <text>
- Сроки: <data> + <text> для доп. комментариев / уточнений по срокам
- Материалы (optinal): <text>
.
.

- Задача: <text>
- Описание / Концепция / Детали задачи: <text>
- Сроки: <data>+ <text> для доп. комментариев / уточнений по срокам
- Материалы (optinal): <text>
'''

short_summary_prompt = f'''Шаблон для создания summary:
Тема обсуждения: <text>

- Задача: <text>
- Описание / Концепция / Детали задачи: <text>
- Сроки: <data> + <text> для доп. комментариев / уточнений по срокам
- Материалы (optinal): <text>
.
.

- Задача: <text>
- Описание / Концепция / Детали задачи: <text>
- Сроки: <data>+ <text> для доп. комментариев / уточнений по срокам
- Материалы (optinal): <text>

Только давай покороче
'''


def get_transcription(audio_file):
    batch_size = 16  # reduce if low on GPU mem
    # change to "int8" if low on GPU mem (may reduce accuracy)

    audio = whisperx.load_audio(audio_file)
    result = model.transcribe(audio, batch_size=batch_size)
    language_code = result["language"]

    # print(result["segments"]) # before alignment

    # # delete model if low on GPU resources
    # # import gc; import torch; gc.collect(); torch.cuda.empty_cache(); del model

    # # 2. Align whisper output
    model_a, metadata = whisperx.load_align_model(
        language_code=language_code, device=device)
    result = whisperx.align(
        result["segments"], model_a, metadata, audio, device, return_char_alignments=False)

    # print(result["segments"]) # after alignment

    # delete model if low on GPU resources
    # import gc; import torch; gc.collect(); torch.cuda.empty_cache(); del model_a

    # 3. Assign speaker labels
    diarize_model = whisperx.diarize.DiarizationPipeline(
        use_auth_token=os.getenv("HF_API_KEY"), device=device)

    # add min/max number of speakers if known
    diarize_segments = diarize_model(audio)
    # diarize_model(audio, min_speakers=min_speakers, max_speakers=max_speakers)

    result = whisperx.assign_word_speakers(diarize_segments, result)
    # print(diarize_segments)
    # print(result["segments"]) # segments are now assigned speaker IDs

    # with open("wiwiw.json", "w", encoding='utf-8') as file:
    #   json.dump(result["segments"], file, ensure_ascii=False, indent=4)

    listToReturn = []

    prev_speaker = None

    for i in result["segments"]:

        speaker = None
        if isinstance(i, dict) and "speaker" in i:
            speaker = i["speaker"]
        else:
            speaker = get_localized("unknown_speaker", language_code)

        if prev_speaker != speaker:
            listToReturn.append(f'{speaker}: {i["text"].strip()}')
            prev_speaker = speaker
        else:
            listToReturn.append(i["text"].strip())

    result = '\n'.join(listToReturn)
    if language_code == "ru":
        result = result.replace("SPEAKER_", "Участник_")

    return result


def get_summary(text="Привет", system_prompt="Сделай саммаризацию"):
    llm_host = os.getenv("LLM_URL")
    url = f"{llm_host}/v1/chat/completions"

    data = {
        "messages": [
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": f'''{text}'''
            }],
        "stream": False
    }

    try:
        response = requests.post(url, json=data)
        response.raise_for_status()

        json_response = response.json()
        if 'choices' in json_response and len(json_response['choices']) and 'message' in json_response['choices'][0] and 'content' in json_response['choices'][0]['message']:
            return json_response['choices'][0]['message']['content']
        else:
            return f'''Ошибка: неверный формат ответа.
Полный ответ:
{json_response}'''

    except requests.exceptions.RequestException as e:
        return f"Ошибка сети: {str(e)}"
    except ValueError:
        return f"Ошибка: ответ не в формате JSON. Текст ответа: {response.text}"


def md_to_text(md):
    html = markdown.markdown(md)
    soup = BeautifulSoup(html, features='html.parser')
    return soup.get_text()


q = queue.Queue()


def worker() -> None:
    print("The queue worker has been started")
    while True:
        item = q.get()
        bot: telebot.TeleBot = item.get("bot")
        message: telebot.types.Message = item.get("message")
        bot_message_id = item.get("bot_message_id")

        code = get_language_code(message)

        bot.edit_message_text(chat_id=message.chat.id,
                              text=get_localized("start_processing", code),
                              message_id=bot_message_id)

        process_audio(message, bot, bot_message_id)

        q.task_done()


def process_audio(message: telebot.types.Message, bot: telebot.TeleBot, bot_message_id: int) -> None:
    code = get_language_code(message)
    try:
        dir_name = f'files/{str(message.chat.id)}_{str(bot_message_id)}'
        os.mkdir(dir_name)

        file_name = ''
        if message.audio:
            file_name = f'{dir_name}/{message.audio.file_name}'

            downloaded_file = bot.download_file(
                bot.get_file(message.audio.file_id).file_path)
        else:
            file_name = f'{dir_name}/voice.ogg'

            downloaded_file = bot.download_file(
                bot.get_file(message.voice.file_id).file_path)

        with open(file_name, 'wb') as new_file:
            new_file.write(downloaded_file)

        transcription = get_transcription(file_name)

        output_file_name = f'{dir_name}/transcription.txt'
        with open(output_file_name, 'w', encoding='utf-8') as f:
            f.write(transcription)

        bot.edit_message_text(chat_id=message.chat.id,
                              message_id=bot_message_id,
                              text=get_localized(
                                  'start_summarization', code))

        result = get_summary(text=transcription, system_prompt=summary_prompt)
        output_file_name = f'{dir_name}/summary.txt'
        with open(output_file_name, 'w', encoding='utf-8') as f:
            f.write(md_to_text(result))

        result = get_summary(text=transcription,
                             system_prompt=short_summary_prompt)
        output_file_name = f'{dir_name}/short_summary.txt'
        with open(output_file_name, 'w', encoding='utf-8') as f:
            f.write(md_to_text(result))

        bot.edit_message_text(chat_id=message.chat.id,
                              message_id=bot_message_id,
                              text=get_localized(
                                  'processing_completed', code),
                              reply_markup=get_base_markup(code))

        print("Done")
    except:
        print("Ошибка обработки аудио")
        bot.edit_message_text(chat_id=message.chat.id,
                              message_id=bot_message_id,
                              text=get_localized("processing_error", code))
    finally:
        try:
            os.remove(file_name)
        except:
            print(f"Error removing file \"{file_name}\"")


def main():
    load_dotenv()

    if not os.path.exists('files'):
        os.mkdir('files')

    # Проверка наличия токенов
    if not (tg_token := os.getenv("TG_API_KEY")):
        raise ValueError("TG_API_KEY не найден в переменных окружения")

    if not (os.getenv("LLM_URL")):
        raise ValueError("LLM_URL не найден в переменных окружения")

    if not os.getenv("HF_API_KEY"):
        print("⚠️ HF_API_KEY не найден - диаризация может не работать")

    bot = telebot.TeleBot(tg_token)

    add_handlers(bot, q)

    threading.Thread(target=worker).start()

    print("🎧 Бот запущен. Ожидание аудиофайлов...")
    bot.infinity_polling()


if __name__ == "__main__":
    main()
