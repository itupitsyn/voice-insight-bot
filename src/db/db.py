from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert
from telebot import types
from src.db.models import User, Transcription, Prompt, Summary
from dotenv import load_dotenv
import os

load_dotenv()
engine = create_engine(os.getenv("DB_URL"))

Session = sessionmaker(engine)


def register_user(message: types.Message) -> None:
    with Session() as session:
        try:
            stmt = insert(User).values(id=message.from_user.id,
                                       user_name=message.from_user.username,
                                       first_name=message.from_user.first_name,
                                       last_name=message.from_user.last_name
                                       ).on_conflict_do_update(
                set_=dict(user_name=message.from_user.username,
                          first_name=message.from_user.first_name,
                          last_name=message.from_user.last_name),
                index_elements=['id']

            )
            session.execute(stmt)
        except:
            session.rollback()
            raise
        else:
            session.commit()


def save_transcription(text: str, message: types.Message, bot_message_id: int) -> None:
    with Session() as session:
        try:
            stmt = insert(Transcription).values(
                user_id=message.from_user.id,
                chat_id=message.chat.id,
                message_id=bot_message_id,
                text=text)
            session.execute(stmt)
        except:
            session.rollback()
            raise
        else:
            session.commit()


def get_transcription(message_id: int, chat_id: int) -> Transcription | None:
    with Session() as session:
        stmt = select(Transcription).where(
            Transcription.chat_id == chat_id,
            Transcription.message_id == message_id
        )
        row = session.execute(stmt).first()
        if row is not None:
            return row[0]

    return None


def get_prompt_by_name(name: str) -> Prompt | None:
    with Session() as session:
        stmt = select(Prompt).where(Prompt.name == name)

        row = session.execute(stmt).first()
        if row is not None:
            return row[0]

    return None


def get_summary(transcription_id: int,  prompt_id: int) -> Summary | None:
    with Session() as session:
        stmt = select(Summary).where(Summary.transcription_id == transcription_id,
                                     Summary.prompt_id == prompt_id)

        row = session.execute(stmt).first()
        if row is not None:
            return row[0]

    return None


def save_summary(text: str, transcription_id: int, prompt_id: int) -> None:
    with Session() as session:
        try:
            stmt = insert(Summary).values(
                transcription_id=transcription_id,
                prompt_id=prompt_id,
                text=text)
            session.execute(stmt)
        except:
            session.rollback()
            raise
        else:
            session.commit()
