from telebot.util import quick_markup
from src.localization import get_localized, get_language_code
from src.utils import (
    get_file_name,
    md_to_text,
    generate_summary,
    limit_text,
    get_full_completed_text,
)
from src.db.db import (
    register_user,
    get_transcription,
    get_summary,
    get_prompt_by_name,
    save_summary,
)

import telebot
import queue
import os
import logging


def get_base_markup(language_code: str):

    return quick_markup(
        {
            get_localized("transcription", language_code): {
                "callback_data": "transcription"
            },
            get_localized("summary", language_code): {"callback_data": "summary"},
            get_localized("short_summary", language_code): {
                "callback_data": "short_summary"
            },
            get_localized("protocol", language_code): {"callback_data": "protocol"},
        },
        row_width=2,
    )


def get_text_processing_markup(language_code: str, text_type: str):
    return quick_markup(
        {
            get_localized("download", language_code): {
                "callback_data": f"download_{text_type}"
            },
            get_localized("show", language_code): {
                "callback_data": f"show_{text_type}"
            },
            get_localized("back", language_code): {"callback_data": "home"},
        },
        row_width=2,
    )


def add_handlers(bot: telebot.TeleBot, q: queue.Queue):
    @bot.message_handler(content_types=["audio", "voice", "video", "document"])
    def add_to_queue(message):
        register_user(message)
        code = get_language_code(message)
        msg = bot.send_message(
            message.chat.id,
            get_localized("file_added_to_queue", code),
            reply_to_message_id=message.id,
        )
        q.put({"bot": bot, "message": message, "bot_message_id": msg.id})

    @bot.message_handler(commands=["start", "help"])
    def send_welcome(message):
        register_user(message)
        code = get_language_code(message)
        bot.send_message(message.chat.id, get_localized("start_answer", code))

    @bot.callback_query_handler(func=lambda call: call.data == "home")
    def send_keyboard(call):
        code = get_language_code(call.message)
        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=get_full_completed_text(code),
            reply_markup=get_base_markup(code),
        )

    @bot.callback_query_handler(
        func=lambda call: call.data == "transcription"
        or call.data == "summary"
        or call.data == "short_summary"
        or call.data == "protocol"
    )
    def handle_button_click(call):
        code = get_language_code(call.message)

        markup = get_text_processing_markup(code, call.data)

        bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=get_localized(call.data, code),
            reply_markup=markup,
        )

    @bot.callback_query_handler(func=lambda call: call.data == "show_transcription")
    def handle_button_click(call):
        msg: telebot.types.Message = call.message
        text_type = "transcription"

        try:
            transcription = get_transcription(msg.id, msg.chat.id)
            if transcription is None:
                bot.answer_callback_query(
                    call.id, f"{text_type} for this message not found"
                )
                return

            code = get_language_code(msg)
            markup = get_text_processing_markup(code, text_type)

            limited_text = limit_text(transcription.text)
            if msg.text.strip() != limited_text.strip():
                bot.edit_message_text(
                    chat_id=msg.chat.id,
                    message_id=msg.message_id,
                    text=limited_text,
                    reply_markup=markup,
                )
        except Exception as e:
            logging.error(e)
            bot.answer_callback_query(call.id, f"{text_type} not found")

    @bot.callback_query_handler(func=lambda call: call.data == "download_transcription")
    def handle_button_click(call):
        msg: telebot.types.Message = call.message
        text_type = "transcription"
        file_name = get_file_name(msg.chat.id, msg.id, text_type)
        code = get_language_code(msg)

        markup = get_text_processing_markup(code, call.data)

        try:
            transcription = get_transcription(msg.id, msg.chat.id)
            if transcription is None:
                bot.answer_callback_query(
                    call.id, f"{text_type} for this message not found"
                )
                return

            with open(file_name, "w", encoding="utf-8") as f:
                f.write(transcription.text)

            with open(file_name, "rt", encoding="utf-8") as file:
                original_message = msg.reply_to_message
                if original_message != None:
                    bot.send_document(
                        msg.chat.id, file, reply_to_message_id=original_message.id
                    )
                else:
                    bot.send_document(msg.chat.id, file, reply_to_message_id=msg.id)

            # send default text_type message and keyboard
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=get_localized(text_type, code),
                reply_markup=markup,
            )
        except:
            bot.edit_message_text(
                chat_id=msg.chat.id,
                message_id=msg.id,
                text=get_localized("unknown_error", code),
                reply_markup=markup,
            )
        finally:
            try:
                os.remove(file_name)
            except:
                logging.error(f'Error removing file "{file_name}"')

    @bot.callback_query_handler(func=lambda call: call.data.startswith("show_"))
    def handle_button_click(call):
        msg: telebot.types.Message = call.message
        text_type = call.data.replace("show_", "", 1)
        code = get_language_code(msg)
        markup = get_text_processing_markup(code, text_type)

        try:
            prompt = get_prompt_by_name(text_type)
            if prompt == None:
                bot.answer_callback_query(
                    call.id, get_localized("unknown_content_type", code)
                )
                return

            transcription = get_transcription(msg.id, msg.chat.id)
            if transcription is None:
                bot.answer_callback_query(
                    call.id, "the transcription for this message not found"
                )
                return

            summary = get_summary(transcription.id, prompt_id=prompt.id)
            content = ""
            if summary is None:
                bot.edit_message_text(
                    chat_id=msg.chat.id,
                    message_id=msg.id,
                    text=get_localized("start_summarization", code),
                )

                content = generate_summary(
                    text=transcription.text, system_prompt=prompt.text
                )
                content = md_to_text(content)
                save_summary(content, transcription.id, prompt.id)
            else:
                content = summary.text

            limited_text = limit_text(content)

            if msg.text.strip() != limited_text.strip():
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=limited_text,
                    reply_markup=markup,
                )
        except Exception as e:
            logging.error(e)
            bot.edit_message_text(
                chat_id=msg.chat.id,
                message_id=msg.id,
                text=get_localized("unknown_error", code),
                reply_markup=markup,
            )

    @bot.callback_query_handler(func=lambda call: call.data.startswith("download_"))
    def handle_button_click(call):
        msg: telebot.types.Message = call.message
        text_type = call.data.replace("download_", "", 1)
        file_name = get_file_name(msg.chat.id, msg.id, text_type)
        code = get_language_code(msg)
        markup = get_text_processing_markup(code, text_type)

        try:
            prompt = get_prompt_by_name(text_type)
            if prompt == None:
                bot.answer_callback_query(
                    call.id, get_localized("unknown_content_type", code)
                )
                return

            transcription = get_transcription(msg.id, msg.chat.id)
            if transcription is None:
                bot.answer_callback_query(
                    call.id, get_localized("transcription_not_found", code)
                )
                return

            summary = get_summary(transcription.id, prompt_id=prompt.id)
            content = ""
            if summary is None:
                bot.edit_message_text(
                    chat_id=msg.chat.id,
                    message_id=msg.id,
                    text=get_localized("start_summarization", code),
                )

                content = generate_summary(
                    text=transcription.text, system_prompt=prompt.text
                )
                content = md_to_text(content)
                save_summary(content, transcription.id, prompt.id)
            else:
                content = summary.text

            with open(file_name, "w", encoding="utf-8") as f:
                f.write(content)

            with open(file_name, "rt", encoding="utf-8") as file:
                original_message = msg.reply_to_message
                if original_message != None:
                    bot.send_document(
                        msg.chat.id, file, reply_to_message_id=original_message.id
                    )
                else:
                    bot.send_document(msg.chat.id, file, reply_to_message_id=msg.id)

            # send default text_type message and keyboard
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=get_localized(text_type, code),
                reply_markup=markup,
            )
        except:
            bot.edit_message_text(
                chat_id=msg.chat.id,
                message_id=msg.id,
                text=get_localized("unknown_error", code),
                reply_markup=markup,
            )
        finally:
            try:
                os.remove(file_name)
            except:
                logging.error(f'Error removing file "{file_name}"')

    @bot.message_handler()
    def handle_message(message: telebot.types.Message):
        if message.reply_to_message is None:
            return

        code = get_language_code(message)
        new_msg = None

        try:
            transcription = get_transcription(
                message.reply_to_message.id, message.chat.id
            )
            transcription_text = message.reply_to_message.text
            if transcription:
                transcription_text = transcription.text

            prompt = message.text

            new_msg = bot.send_message(
                message.chat.id,
                reply_to_message_id=message.id,
                text=get_localized("start_summarization", code),
            )

            summary = generate_summary(transcription_text, prompt)
            summary = md_to_text(summary)

            bot.edit_message_text(
                chat_id=new_msg.chat.id,
                message_id=new_msg.message_id,
                text=limit_text(summary),
            )

        except Exception as e:
            logging.error(e)
            bot.send_message(
                message.chat.id,
                reply_to_message_id=message.id,
                text=get_localized("unknown_error", code),
            )
