FROM emptynull/whisperx-cuda:latest

WORKDIR /root


COPY .env main.py ./src alembic.ini ./migration ./

ENV PYTHONUNBUFFERED=1

CMD ["python3", "main.py"]

