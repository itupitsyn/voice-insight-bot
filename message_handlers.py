import telebot
from telebot.util import quick_markup
from localization import get_localized, get_language_code
import queue


def add_handlers(bot: telebot.TeleBot, q: queue.Queue):
    @bot.message_handler(content_types=['audio', 'voice'])
    def add_to_queue(message):
        code = get_language_code(message)
        bot.send_message(message.chat.id,
                         get_localized('file_added_to_queue', code),
                         reply_to_message_id=message.id)
        q.put({"bot": bot, "message": message})

    @bot.message_handler(commands=['start'])
    def send_welcome(message):
        code = get_language_code(message)
        bot.send_message(
            message.chat.id,
            get_localized('start_answer', code))

    def get_base_markup(language_code: str):

        return quick_markup({
            get_localized('transcription', language_code): {'callback_data': 'transcription'},
            get_localized('summary', language_code): {'callback_data': 'summary'},
            get_localized('short_summary', language_code): {'callback_data': 'short_summary'},
        }, row_width=2)

    @bot.message_handler(commands=['privetiki'])
    def send_keyboard(message):
        code = get_language_code(message)
        bot.reply_to(message,
                     get_localized('processing_completed', code),
                     reply_markup=get_base_markup(code))

    @bot.callback_query_handler(func=lambda call: call.data == "home")
    def send_keyboard(call):
        code = get_language_code(call.message)
        bot.edit_message_text(chat_id=call.message.chat.id,
                              message_id=call.message.message_id,
                              text=get_localized('processing_completed', code),
                              reply_markup=get_base_markup(code))

    @bot.callback_query_handler(func=lambda call: call.data == "transcription" or call.data == 'summary' or call.data == 'short_summary')
    def handle_button_click(call):
        # Acknowledge the callback
        # bot.answer_callback_query(call.id, "You clicked the button!")
        code = get_language_code(call.message)

        markup = quick_markup({
            get_localized('download', code): {'callback_data': f'download_{call.data}'},
            get_localized('copy', code): {'callback_data': f'copy_{call.data}'},
            get_localized('back', code): {'callback_data': 'home'},
        }, row_width=2)

        bot.edit_message_text(chat_id=call.message.chat.id,
                              message_id=call.message.message_id,
                              text=get_localized('chose_option', code),
                              reply_markup=markup)
