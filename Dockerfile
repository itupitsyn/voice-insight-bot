FROM nvidia/cuda:12.0.0-devel-ubuntu20.04

WORKDIR /root

COPY main.py .env ./

RUN apt update -y && DEBIAN_FRONTEND=noninteractive apt install -y ffmpeg \
python3 python3-pip libcudnn8 libcudnn8-dev

RUN pip3 install whisperx dotenv requests beautifulsoup4 markdown telebot \
&& pip3 install transformers -U

CMD ["python3", "main.py"]

