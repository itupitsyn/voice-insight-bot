import whisperx
from dotenv import load_dotenv
import os
import shutil
import requests

import markdown  # pip install markdown
from bs4 import BeautifulSoup  # pip install beautifulsoup4

import telebot

import threading
import queue

device = "cuda"
compute_type = "float16"

print("Start loading model")
# 1. Transcribe with original whisper (batched)
model = whisperx.load_model("large-v2", device, compute_type=compute_type)

# save model to local path (optional)
# model_dir = "/path/"
# model = whisperx.load_model("large-v2", device, compute_type=compute_type, download_root=model_dir)


def get_transcription(audio_file):
    batch_size = 16  # reduce if low on GPU mem
    # change to "int8" if low on GPU mem (may reduce accuracy)

    audio = whisperx.load_audio(audio_file)
    result = model.transcribe(audio, batch_size=batch_size)
    # print(result["segments"]) # before alignment

    # # delete model if low on GPU resources
    # # import gc; import torch; gc.collect(); torch.cuda.empty_cache(); del model

    # # 2. Align whisper output
    model_a, metadata = whisperx.load_align_model(
        language_code=result["language"], device=device)
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

    for i in result["segments"]:
        if isinstance(i, dict) and "speaker" in i:
            listToReturn.append(f'{i["speaker"]}: {i["text"].strip()}')
        else:
            listToReturn.append(f'Неизвестный участник: {i["text"].strip()}')

    return '\n'.join(listToReturn)


def get_summary(text="Привет"):
    llm_host = os.getenv("LLM_URL")
    url = f"{llm_host}/v1/chat/completions"

    data = {
        "messages": [
            {
                "role": "system",
                "content": f'''Шаблон для создания summary: 
Тема обсуждения: <text>

- Задача: <text>
- Описание / Концепция / Детали задачи: <text>
- Сроки: <data> + <text> для доп. комментариев / уточнений по срокам
- Материалы (optinal): <text> 
.
.
.

- Задача: <text>
- Описание / Концепция / Детали задачи: <text>
- Сроки: <data>+ <text> для доп. комментариев / уточнений по срокам
- Материалы (optinal): <text>
'''
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
        bot = item.get("bot")
        message = item.get("message")

        bot.send_message(message.chat.id, "Начинаем обработку файла",
                         reply_to_message_id=message.id)

        process_audio(message, bot)

        q.task_done()


def process_audio(message, bot) -> None:
    try:
        os.mkdir(f'files/{str(message.id)}')

        file_name = ''
        if message.audio:
            file_name = f'files/{message.id}/{message.audio.file_name}'

            downloaded_file = bot.download_file(
                bot.get_file(message.audio.file_id).file_path)
        else:
            file_name = f'files/{message.id}/{message.voice.file_id}.ogg'

            downloaded_file = bot.download_file(
                bot.get_file(message.voice.file_id).file_path)

        with open(file_name, 'wb') as new_file:
            new_file.write(downloaded_file)

        result = get_transcription(file_name)

        output_file_name = f'files/{str(message.id)}/transcription.txt'
        with open(output_file_name, 'w', encoding='utf-8') as f:
            f.write(result)

        with open(output_file_name, 'rt', encoding='utf-8') as f:
            bot.send_document(message.chat.id, f,
                              reply_to_message_id=message.id)

        print("Starting the summarization")

        bot.send_message(message.chat.id, "Запускаем саммаризацию",
                         reply_to_message_id=message.id)

        summary = get_summary(text=result.replace("SPEAKER_", "Участник_"))

        print("Sending the summarization result")

        bot.send_message(message.chat.id, md_to_text(
            summary), reply_to_message_id=message.id)

        print("Done")
    except:
        print("Ошибка обработки аудио")
        bot.send_message(message.chat.id, "Ошибка обработки аудио",
                         reply_to_message_id=message.id)
    finally:
        shutil.rmtree(str(f'files/{message.id}'))


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

    threading.Thread(target=worker).start()

    @bot.message_handler(content_types=['audio', 'voice'])
    def add_to_queue(message):
        bot.send_message(message.chat.id, "Файл добавлен в очередь",
                         reply_to_message_id=message.id)
        q.put({"bot": bot, "message": message})

    @bot.message_handler(commands=['start'])
    def send_welcome(message):
        bot.send_message(
            message.chat.id, "Отправьте аудиофайл или голосовое сообщение для получения саммари")

    print("🎧 Бот запущен. Ожидание аудиофайлов...")
    bot.infinity_polling()


if __name__ == "__main__":
    main()
