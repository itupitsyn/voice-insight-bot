import markdown  # pip install markdown
import os
import requests
import logging

from src.localization import get_localized
from src.db.db import (
    get_user,
    create_user,
    save_transcription,
    save_summary,
    get_transcription,
    get_prompt_by_name,
)

from bs4 import BeautifulSoup  # pip install beautifulsoup4

MESSAGE_LIMIT = 4096


def get_dir_name(chat_id: int, msg_id: int):
    return f"files/{str(chat_id)}_{str(msg_id)}"


def get_file_name(chat_id: int, msg_id: int, text_type: str) -> str:
    return f"files/{str(chat_id)}_{str(msg_id)}_{text_type}.txt"


def md_to_text(md):
    html = markdown.markdown(md)
    soup = BeautifulSoup(html, features="html.parser")
    return soup.get_text()


def generate_transcription(audio_file):
    url = "http://192.168.1.90:8000/v1/audio/transcriptions"
    files = {"file": open(audio_file, "rb")}
    data = {"diarize": True}

    response = requests.post(url, files=files, data=data)
    responseData = response.json()

    language_code = responseData["language"]

    listToReturn = []

    prev_speaker = None

    for i in responseData["segments"]:
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

    result = "\n".join(listToReturn)
    if language_code == "ru":
        result = result.replace("SPEAKER_", "Участник_")

    return result


def generate_summary(text="Привет", system_prompt="Сделай саммаризацию"):
    llm_host = os.getenv("LLM_URL")
    url = f"{llm_host}/v1/chat/completions"

    data = {
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"""{text}"""},
        ],
        "stream": False,
    }

    response = requests.post(url, json=data)
    response.raise_for_status()

    json_response = response.json()
    if (
        "choices" in json_response
        and len(json_response["choices"])
        and "message" in json_response["choices"][0]
        and "content" in json_response["choices"][0]["message"]
    ):
        return json_response["choices"][0]["message"]["content"]
    else:
        raise ValueError(
            f"""Ошибка: неверный формат ответа.
Полный ответ:
{json_response}"""
        )


def migrate_data_from_files():
    folder = "files"

    short_summary_prompt = get_prompt_by_name("short_summary")
    summary_prompt = get_prompt_by_name("summary")
    protocol_prompt = get_prompt_by_name("protocol")

    for foldername in os.listdir(folder):

        if not os.path.isdir(f"{folder}/{foldername}"):
            continue

        parts = foldername.split("_")
        user_id = int(parts[0])
        message_id = int(parts[1])

        usr = get_user(user_id)
        if usr == None:
            create_user(user_id, str(user_id))

        for filename in os.listdir(f"{folder}/{foldername}"):
            fullkek = f"{folder}/{foldername}/{filename}"
            if not os.path.isfile(fullkek) or not filename.startswith("transcription"):
                continue

            with open(fullkek, "rt", encoding="utf-8") as file:
                text = file.read()
                save_transcription(text, user_id, user_id, message_id)
                break

        transcription = get_transcription(message_id, user_id)
        if transcription == None:
            logging.error(f"TRANSCRIPTION NOT FOUND FOR {foldername}")
            continue

        for filename in os.listdir(f"{folder}/{foldername}"):
            fullkek = f"{folder}/{foldername}/{filename}"
            if not os.path.isfile(fullkek) or filename.startswith("transcription"):
                continue

            with open(fullkek, "rt", encoding="utf-8") as file:
                text = file.read()
                if filename.startswith("short_summary"):
                    save_summary(text, transcription.id, short_summary_prompt.id)
                elif filename.startswith("summary"):
                    save_summary(text, transcription.id, summary_prompt.id)
                elif filename.startswith("protocol"):
                    save_summary(text, transcription.id, protocol_prompt.id)


def get_full_completed_text(code: str) -> str:
    text = get_localized("processing_completed", code)
    text += f"\n{get_localized('transcription_result_hint', code)}"

    return text


def limit_text(text: str) -> str:
    if len(text) > MESSAGE_LIMIT:
        return text[: MESSAGE_LIMIT - 3] + "..."

    return text
