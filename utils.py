import whisperx
import markdown  # pip install markdown
import os
import requests
import telebot
from localization import get_localized
from prompts import short_summary_prompt, summary_prompt, protocol_prompt
from os.path import isfile
from localization import get_localized, get_language_code
from bs4 import BeautifulSoup  # pip install beautifulsoup4


def get_dir_name(chat_id: int, msg_id: int):
    return f'files/{str(chat_id)}_{str(msg_id)}'


def md_to_text(md):
    html = markdown.markdown(md)
    soup = BeautifulSoup(html, features='html.parser')
    return soup.get_text()


device = "cuda"
compute_type = "float16"

print("Start loading model")

# 1. Transcribe with original whisper (batched)

# save model to local path (optional)
# model_dir = "/path/"
# model = whisperx.load_model("large-v2", device, compute_type=compute_type, download_root=model_dir)

model = whisperx.load_model("large-v2", device, compute_type=compute_type)


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


def generate_content_if_not_exist(text_type: str, message: telebot.types.Message, bot: telebot.TeleBot) -> None:
    dir_name = get_dir_name(message.chat.id, message.id)
    file_name = text_type + ".txt"
    file_full_name = f"{dir_name}/{file_name}"
    code = get_language_code(message)

    if text_type == 'transcription' or isfile(file_full_name):
        return

    transcription = ''
    with open(f"{dir_name}/transcription.txt", "rt", encoding='utf-8') as file:
        transcription = file.read()

    bot.edit_message_text(chat_id=message.chat.id,
                          message_id=message.message_id,
                          text=get_localized(
                              'start_summarization', code))

    prompt = protocol_prompt
    if text_type == 'summary':
        prompt = summary_prompt
    elif text_type == 'short_summary':
        text_type = short_summary_prompt

    result = get_summary(text=transcription,
                         system_prompt=prompt)
    with open(file_full_name, 'w', encoding='utf-8') as f:
        f.write(md_to_text(result))
