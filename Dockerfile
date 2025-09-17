FROM emptynull/whisperx-cuda:latest

WORKDIR /root


COPY .env main.py localization.py message_handlers.py utils.py prompts.py ./

ENV PYTHONUNBUFFERED=1

CMD ["python3", "main.py"]

