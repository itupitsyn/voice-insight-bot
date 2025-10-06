import whisperx
import markdown  # pip install markdown
import os
import requests

from src.localization import get_localized
from src.db.db import get_user, create_user, save_transcription, save_summary, get_transcription, get_prompt_by_name

from bs4 import BeautifulSoup  # pip install beautifulsoup4


def get_dir_name(chat_id: int, msg_id: int):
    return f'files/{str(chat_id)}_{str(msg_id)}'


def get_file_name(chat_id: int, msg_id: int, text_type: str) -> str:
    return f'files/{str(chat_id)}_{str(msg_id)}_{text_type}.txt'


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


def generate_transcription(audio_file):
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


def generate_summary(text="Привет", system_prompt="Сделай саммаризацию"):
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


def migrate_data_from_files():
    folder = "files"

    short_summary_prompt = get_prompt_by_name("short_summary")
    summary_prompt = get_prompt_by_name("summary")
    protocol_prompt = get_prompt_by_name("protocol")

    for foldername in os.listdir(folder):

        if not os.path.isdir(f'{folder}/{foldername}'):
            continue

        parts = foldername.split("_")
        user_id = int(parts[0])
        message_id = int(parts[1])

        usr = get_user(user_id)
        if usr == None:
            create_user(user_id, str(user_id))

        for filename in os.listdir(f'{folder}/{foldername}'):
            fullkek = f'{folder}/{foldername}/{filename}'
            if not os.path.isfile(fullkek) or not filename.startswith("transcription"):
                continue

            with open(fullkek, "rt", encoding='utf-8') as file:
                text = file.read()
                save_transcription(text, user_id, user_id, message_id)
                break

        transcription = get_transcription(message_id, user_id)
        if transcription == None:
            print(f"TRANSCRIPTION NOT FOUND FOR {foldername}")
            continue

        for filename in os.listdir(f'{folder}/{foldername}'):
            fullkek = f'{folder}/{foldername}/{filename}'
            if not os.path.isfile(fullkek) or filename.startswith("transcription"):
                continue

            with open(fullkek, "rt", encoding='utf-8') as file:
                text = file.read()
                if filename.startswith("short_summary"):
                    save_summary(text, transcription.id,
                                 short_summary_prompt.id)
                elif filename.startswith("summary"):
                    save_summary(text, transcription.id, summary_prompt.id)
                elif filename.startswith("protocol"):
                    save_summary(text, transcription.id, protocol_prompt.id)


def get_full_completed_text(code: str) -> str:
    text = get_localized('processing_completed', code)
    text += f"\n{get_localized('transcription_result_hint', code)}"

    return text
