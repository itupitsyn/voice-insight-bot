from dotenv import load_dotenv
import os
import requests

import telebot

import threading
import queue

from localization import get_localized, get_language_code

from message_handlers import add_handlers, get_base_markup
from utils import get_dir_name, get_summary, get_transcription, md_to_text
from prompts import short_summary_prompt, summary_prompt
from subprocess import run

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

        process_message(message, bot, bot_message_id)

        q.task_done()


def process_message(message: telebot.types.Message, bot: telebot.TeleBot, bot_message_id: int) -> None:
    code = get_language_code(message)
    file_name = ''
    try:
        file_api = os.getenv('TG_FILES_API_ADDRESS')
        tg_api = os.getenv('TG_API_KEY')
        file_url = f'{file_api}/file/bot{tg_api}'

        dir_name = get_dir_name(message.chat.id, bot_message_id)
        os.mkdir(dir_name)

        file_server_path = ""
        if message.audio or message.voice:
            if message.audio:
                file_name = f'{dir_name}/{message.audio.file_name}'
                file_server_path = bot.get_file(message.audio.file_id)

            elif message.voice:
                file_name = f'{dir_name}/voice.ogg'
                file_server_path = bot.get_file(
                    message.voice.file_id).file_path

            file_full_server_path = f"{file_url}{file_server_path}"

            response = requests.get(file_full_server_path)

            with open(file_name, 'wb') as file:
                file.write(response.content)

        else:
            video_file_name = ""
            video_file_server_path = ""

            if message.video:
                video_file_name = f'{dir_name}/{message.video.file_name}'
                video_file_server_path = bot.get_file(
                    message.video.file_id).file_path

            elif message.document:
                video_file_name = f'{dir_name}/{message.document.file_name}'
                video_file_server_path = bot.get_file(
                    message.document.file_id).file_path

            else:
                bot.edit_message_text(chat_id=message.chat.id,
                                      message_id=bot_message_id,
                                      text=get_localized("unknown_content_type", code))
                return
            response = requests.get(f'{file_url}{video_file_server_path}')

            with open(video_file_name, 'wb') as file:
                file.write(response.content)

            file_name = f"{dir_name}/audio.aac"
            cmd = [
                "ffmpeg",
                "-i",
                video_file_name,
                "-vn",
                "-acodec",
                "copy",
                file_name
            ]

            run(cmd, check=True)
            os.remove(video_file_name)

        process_audio(file_name, message, bot, bot_message_id)

        print("Done")

    except Exception as e:
        print("Ошибка обработки аудио")
        print(e)
        bot.edit_message_text(chat_id=message.chat.id,
                              message_id=bot_message_id,
                              text=get_localized("processing_error", code))

    finally:
        try:
            os.remove(file_name)
        except:
            print(f"Error removing file \"{file_name}\"")


def process_audio(audio_file_name: str, message: telebot.types.Message, bot: telebot.TeleBot, bot_message_id: int):
    dir_name = get_dir_name(message.chat.id, bot_message_id)
    code = get_language_code(message)
    transcription = get_transcription(audio_file_name)

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

    api_addr = os.getenv("TG_API_ADDRESS")
    if not api_addr:
        raise ValueError("Локальный адрес для бота не установлен!")

    if not os.getenv("TG_FILES_API_ADDRESS"):
        raise ValueError("Локальный адрес для файлов бота не установлен!")

    telebot.apihelper.API_URL = api_addr + "/bot{0}/{1}"

    add_handlers(bot, q)

    threading.Thread(target=worker).start()

    print("🎧 Бот запущен. Ожидание аудиофайлов...")
    bot.infinity_polling()


if __name__ == "__main__":
    main()
