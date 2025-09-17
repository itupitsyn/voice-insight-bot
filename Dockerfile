FROM emptynull/whisperx-cuda:latest

WORKDIR /root

COPY .env main.py localization.py message_handlers.py utils.py prompts.py ./

CMD ["python3", "main.py"]

