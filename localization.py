localization = {
    "transcription": {
        "default": "Transcription",
        "ru": "Транскрипция"
    },
    "summary": {
        "default": "Summary",
        "ru": "Саммари"
    },
    "short_summary": {
        "default": "Short summary",
        "ru": "Укороченное саммари"
    },
    "file_added_to_queue": {
        "default": "File added to queue",
        "ru": "Файл добавлен в очередь"
    },
    "start_answer": {
        "default": '''Hi friend 👋 We know how much time you spend in meetings and calls, how many details you need to keep track of, and how easy it is to get lost in the flow of information! That's why we created a bot for you that can transcribe audio recordings of calls and video meetings 📞.

Click the paperclip 📎 and upload a call file, video meeting recording, or record your voice → our smart bot 🤖 will analyze the call → you'll get:
✔️ a brief summary outlining the main concept of the meeting
✔️ a full summary with detailed conversation topics
✔️ a call transcript to dive into the details of the call

You can copy and forward each item as a message or download it as a file!''',
        "ru": '''Привет, друг 👋 Мы знаем как много времени приходится проводить на встречах и созвонах, сколько деталей нужно учесть и не потеряться в потоке информации! Для тебя мы создали бота, который умеет транскрибировать аудиозаписи звонков и видеовстреч 📞. 

Нажми на скрепку 📎 и загрузи файл звонка, видеовстречи или запиши voice → наш умный бот 🤖 проанализирует звонок → ты получишь:
✔️ краткое саммари, где изложена основная концепция встречи
✔️ полное саммари, где можно увидеть детализированные топики разговора
✔️ транскрипцию звонка, чтобы погрузиться в детали звонка

Каждый пункт можно скопировать и переслать в виде сообщения или загрузить файлом!'''
    },
    "processing_completed": {
        "default": "Processing completed",
        "ru": "Обработка завершена"
    },
    "download": {
        "default": "Download",
        "ru": "Скачать"
    },
    "show": {
        "default": "Show",
        "ru": "Показать"
    },
    "back": {
        "default": "Back",
        "ru": "Назад"
    },
    "chose_option": {
        "default": "Chose the option",
        "ru": "Выберите вариант"
    },
    "start_processing": {
        "default": "File processing has been started",
        "ru": "Начинаем обработку файла"
    },
    "start_summarization": {
        "default": "Summarization has been started",
        "ru": "Запускаем саммаризацию"
    },
    "processing_error": {
        "default": "Audio processing error",
        "ru": "Ошибка обработки аудио"
    },
    "unknown_speaker": {
        "default": "Unknown speaker",
        "ru": "Неизвестный участник"
    },
    "unknown_content_type": {
        "default": "Unknown content type",
        "ru": "Неизвестный тип контента"
    }
}


def get_localized(phraze_key: str, language_code: str) -> str:
    phraze = localization.get(phraze_key)
    if (not phraze):
        return ''

    localized = phraze.get(language_code)

    if (localized):
        return localized

    localized = phraze.get("default")

    if (localized):
        return localized

    return ""


def get_language_code(message):
    if (message == None):
        return "en"

    if (message.from_user.language_code):
        return message.from_user.language_code

    return get_language_code(message.reply_to_message)
