FROM tiangolo/uwsgi-nginx-flask:python3.8

ENV PYTHONUNBUFFERED 1

WORKDIR /ffmpegapp

COPY . .

RUN apt-get update && apt-get install -y ffmpeg

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["python", "app.py"]
