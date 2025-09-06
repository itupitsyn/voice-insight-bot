FROM emptynull/whisperx-cuda:latest

WORKDIR /root

COPY main.py .env localization.py message_handlers.py ./

CMD ["python3", "main.py"]

