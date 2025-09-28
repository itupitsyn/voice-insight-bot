FROM emptynull/whisperx-cuda:latest

WORKDIR /root

RUN pip3 install SQLAlchemy psycopg2-binary alembic

COPY .env main.py ./src alembic.ini ./migration ./

ENV PYTHONUNBUFFERED=1

CMD ["python3", "main.py"]

