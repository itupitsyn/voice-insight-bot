import os
import requests
import telebot
import threading
import queue
import shutil
import logging

from dotenv import load_dotenv
from subprocess import run
from src.localization import get_localized, get_language_code
from src.message_handlers import add_handlers, get_base_markup
from src.utils import get_dir_name, generate_transcription, get_full_completed_text
from src.db.db import save_transcription

q = queue.Queue()

logging.basicConfig(
    format="%(filename)s[LINE:%(lineno)d]# %(levelname)-8s [%(asctime)s]  %(message)s",
    level=logging.INFO,
)


def worker() -> None:
    logging.info("The queue worker has been started")
    while True:
        item = q.get()
        bot: telebot.TeleBot = item.get("bot")
        message: telebot.types.Message = item.get("message")
        bot_message_id = item.get("bot_message_id")

        code = get_language_code(message)

        bot.edit_message_text(
            chat_id=message.chat.id,
            text=get_localized("start_processing", code),
            message_id=bot_message_id,
        )

        process_message(message, bot, bot_message_id)

        q.task_done()


def process_message(
    message: telebot.types.Message, bot: telebot.TeleBot, bot_message_id: int
) -> None:
    code = get_language_code(message)
    dir_name = get_dir_name(message.chat.id, bot_message_id)
    file_name = ""
    try:
        file_api = os.getenv("TG_FILES_API_ADDRESS")
        tg_api = os.getenv("TG_API_KEY")
        file_url = f"{file_api}/file/bot{tg_api}"

        os.mkdir(dir_name)

        file_server_path = ""
        if message.audio or message.voice:
            if message.audio:
                file_name = f"{dir_name}/{message.audio.file_name}"
                file_server_path = bot.get_file(message.audio.file_id).file_path

            elif message.voice:
                file_name = f"{dir_name}/voice.ogg"
                file_server_path = bot.get_file(message.voice.file_id).file_path

            file_full_server_path = f"{file_url}{file_server_path}"

            response = requests.get(file_full_server_path)

            with open(file_name, "wb") as file:
                file.write(response.content)

        else:
            video_file_name = ""
            video_file_server_path = ""

            if message.video:
                video_file_name = f"{dir_name}/{message.video.file_name}"
                for i in range(3):
                    try:
                        video_file_server_path = bot.get_file(
                            message.video.file_id
                        ).file_path
                        break
                    except Exception as e:
                        logging.error(e)
                        if i < 2:
                            continue
                        raise e

            elif message.document:
                video_file_name = f"{dir_name}/{message.document.file_name}"
                video_file_server_path = bot.get_file(
                    message.document.file_id
                ).file_path

            else:
                bot.edit_message_text(
                    chat_id=message.chat.id,
                    message_id=bot_message_id,
                    text=get_localized("unknown_content_type", code),
                )
                return
            response = requests.get(f"{file_url}{video_file_server_path}")

            with open(video_file_name, "wb") as file:
                file.write(response.content)

            file_name = f"{dir_name}/audio.aac"

            run(
                f'ffmpeg -i "{video_file_name}" -acodec aac -b:a 192k "{file_name}"',
                shell=True,
                check=True,
            )
            os.remove(video_file_name)

        process_audio(file_name, message, bot, bot_message_id)

        logging.info("Done")
    except Exception as e:
        logging.error("Ошибка обработки аудио")
        logging.error(e)
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=bot_message_id,
            text=get_localized("processing_error", code),
        )
    finally:
        try:
            shutil.rmtree(dir_name)
        except:
            logging.error(f'Error removing "{dir_name}"')


def process_audio(
    audio_file_name: str,
    message: telebot.types.Message,
    bot: telebot.TeleBot,
    bot_message_id: int,
):
    code = get_language_code(message)
    transcription = generate_transcription(audio_file_name)
    save_transcription(
        transcription, message.from_user.id, message.chat.id, bot_message_id
    )

    bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=bot_message_id,
        text=get_full_completed_text(code),
        reply_markup=get_base_markup(code),
    )


def main():
    load_dotenv()

    if not os.path.exists("files"):
        os.mkdir("files")

    # Проверка наличия токенов
    if not (tg_token := os.getenv("TG_API_KEY")):
        raise ValueError("TG_API_KEY не найден в переменных окружения")

    if not (os.getenv("LLM_URL")):
        raise ValueError("LLM_URL не найден в переменных окружения")

    if not os.getenv("WHISPERX_API_ADDRESS"):
        raise ValueError(
            "WHISPERX_API_ADDRESS не найден - диаризация может не работать"
        )

    bot = telebot.TeleBot(tg_token)

    api_addr = os.getenv("TG_API_ADDRESS")
    if not api_addr:
        raise ValueError("Локальный адрес для бота не установлен!")

    if not os.getenv("TG_FILES_API_ADDRESS"):
        raise ValueError("Локальный адрес для файлов бота не установлен!")

    telebot.apihelper.API_URL = api_addr + "/bot{0}/{1}"

    add_handlers(bot, q)

    threading.Thread(target=worker).start()

    logging.info("🎧 Бот запущен. Ожидание аудиофайлов...")
    bot.infinity_polling()


if __name__ == "__main__":
    main()
