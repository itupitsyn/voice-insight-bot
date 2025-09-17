import telebot
from telebot.util import quick_markup
from localization import get_localized, get_language_code
import queue
from utils import get_dir_name

MESSAGE_LIMIT = 4096


def get_base_markup(language_code: str):

    return quick_markup({
        get_localized('transcription', language_code): {'callback_data': 'transcription'},
        get_localized('summary', language_code): {'callback_data': 'summary'},
        get_localized('short_summary', language_code): {'callback_data': 'short_summary'},
    }, row_width=2)


def get_text_processing_markup(language_code: str, text_type: str):
    return quick_markup({
        get_localized('download', language_code): {'callback_data': f'download_{text_type}'},
        get_localized('show', language_code): {'callback_data': f'show_{text_type}'},
        get_localized('back', language_code): {'callback_data': 'home'},
    }, row_width=2)


def add_handlers(bot: telebot.TeleBot, q: queue.Queue):
    @bot.message_handler(content_types=['audio', 'voice', 'video', 'document'])
    def add_to_queue(message):
        code = get_language_code(message)
        msg = bot.send_message(message.chat.id,
                               get_localized('file_added_to_queue', code),
                               reply_to_message_id=message.id)
        q.put({"bot": bot, "message": message, "bot_message_id": msg.id})

    @bot.message_handler(commands=['start', 'help'])
    def send_welcome(message):
        code = get_language_code(message)
        bot.send_message(
            message.chat.id,
            get_localized('start_answer', code))

    @bot.callback_query_handler(func=lambda call: call.data == "home")
    def send_keyboard(call):
        code = get_language_code(call.message)
        bot.edit_message_text(chat_id=call.message.chat.id,
                              message_id=call.message.message_id,
                              text=get_localized('processing_completed', code),
                              reply_markup=get_base_markup(code))

    @bot.callback_query_handler(func=lambda call: call.data == "transcription" or call.data == 'summary' or call.data == 'short_summary')
    def handle_button_click(call):
        code = get_language_code(call.message)

        markup = get_text_processing_markup(code, call.data)

        bot.edit_message_text(chat_id=call.message.chat.id,
                              message_id=call.message.message_id,
                              text=get_localized(call.data, code),
                              reply_markup=markup)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("show_"))
    def handle_button_click(call):

        dir_name = get_dir_name(call.message.chat.id, call.message.id)
        text_type = call.data.replace("show_", "", 1)
        file_name = text_type + ".txt"

        try:
            with open(f"{dir_name}/{file_name}", "rt", encoding='utf-8') as file:
                content = file.read()
                code = get_language_code(call.message)
                markup = get_text_processing_markup(code, text_type)

                if len(content) > MESSAGE_LIMIT:
                    content = content[:MESSAGE_LIMIT-3] + "..."

                bot.edit_message_text(chat_id=call.message.chat.id,
                                      message_id=call.message.message_id,
                                      text=content,
                                      reply_markup=markup)
        except Exception as e:
            print(e)
            bot.answer_callback_query(call.id, f"{text_type} not found")

    @bot.callback_query_handler(func=lambda call: call.data.startswith("download_"))
    def handle_button_click(call):

        dir_name = get_dir_name(call.message.chat.id, call.message.id)
        text_type = call.data.replace("download_", "", 1)
        file_name = text_type + ".txt"

        try:
            with open(f"{dir_name}/{file_name}", "rt", encoding='utf-8') as file:

                original_message = call.message.reply_to_message
                if original_message != None:
                    bot.send_document(call.message.chat.id, file,
                                      reply_to_message_id=original_message.id)
                else:
                    bot.send_document(call.message.chat.id, file,
                                      reply_to_message_id=call.message.id)

        except:
            bot.answer_callback_query(call.id, f"{text_type} not found")
