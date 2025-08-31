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
        "default": "Send an audio or a voice message to get the summary",
        "ru": "Отправьте аудиофайл или голосовое сообщение для получения саммари"
    },
    "processing_completed": {
        "default": "Processing completed",
        "ru": "Обработка завершена"
    },
    "download": {
        "default": "Download",
        "ru": "Скачать"
    },
    "copy": {
        "default": "Copy",
        "ru": "Копировать"
    },
    "back": {
        "default": "Back",
        "ru": "Назад"
    },
    "chose_option": {
        "default": "Chose the option",
        "ru": "Выберите вариант"
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

