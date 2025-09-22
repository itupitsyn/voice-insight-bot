from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.postgresql import insert
from telebot import types
from src.db.models import User

engine = create_engine(
    "postgresql://voice-insight-bot:voice-insight-bot@localhost:5432/voice-insight-bot", echo=True)

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

def save_transcription(text: string, message: types.Message) -> Non
