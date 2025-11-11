FROM python:3.10.19-alpine3.21

WORKDIR /root

RUN apk update && apk add --no-cache ffmpeg
RUN pip3 install SQLAlchemy psycopg2-binary alembic requests telebot dotenv markdown beautifulsoup4

COPY .env main.py alembic.ini ./
COPY src ./src
COPY migration ./migration

ENV PYTHONUNBUFFERED=1

CMD ["python3", "main.py"]

