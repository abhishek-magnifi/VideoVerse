import os
import subprocess
from flask import Flask, request, jsonify
import time
import requests
import threading
import logging
import uuid


app = Flask(__name__)
logging.basicConfig(level=logging.INFO)


def _notify_clients(message):
    for client in sse_clients:
        client.send(message, event="error")

def process_single_transition(video_urls):
    start = time.time()
    video_durations = []

    try:
        ffmpeg_command = ['ffmpeg']
        for video_url in video_urls:
            ffprobe_command = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', video_url]
            duration = int(float(subprocess.check_output(ffprobe_command).decode('utf-8').strip()))
            video_durations.append(duration)
            ffmpeg_command.extend(['-i', video_url])
            print(video_durations)

        video_filter_parts = []
        audio_filter_parts = []
        offset = 0

        for idx, duration in enumerate(video_durations):
            if idx == (len(video_durations)-1):
                break
            if idx == 0:
                offset += duration - 1
                video_filter_parts.append(f'[{idx}:v][{idx+1}:v]xfade=transition=fade:duration=1:offset={offset},format=yuv420p[v{idx}]')
                audio_filter_parts.append(f'[{idx}:a][{idx+1}:a]acrossfade=d=1[a{idx}]')
            elif idx < len(video_durations):
                offset += duration - 1
                video_filter_parts.append(f'[v{idx-1}][{idx+1}:v]xfade=transition=fade:duration=1:offset={offset},format=yuv420p[v{idx}]')
                audio_filter_parts.append(f'[a{idx-1}][{idx+1}:a]acrossfade=d=1[a{idx}]')

            mapping_options = ['-map', f'[v{idx}]', '-map', f'[a{idx}]']

        video_filter_complex = ';'.join(video_filter_parts)
        audio_filter_complex = ';'.join(audio_filter_parts)

        filter_complex = f'{video_filter_complex};{audio_filter_complex}'
        ffmpeg_command.extend(['-filter_complex', filter_complex] + mapping_options + [f'ffmpegapp/transition_video_{uuid.uuid4()}.mp4'])
        print(ffmpeg_command)
        start4 = time.time()
        process = subprocess.run(ffmpeg_command, capture_output=True)
        print(process.stderr)
        process.check_returncode()

        end = time.time()
        print("ffmpeg time", end-start4)
        print("timeeeeeee***", end-start)
        print(f"Transition video created: 'transition_video.mp4'")

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        notify_clients(e)
        raise


@app.route('/transition', methods=['POST'])
def transition():

    data = request.json
    if 'video_urls' not in data:
        return jsonify({'error': 'No video URLs found in the request.'}), 400

    video_urls = data['video_urls']

    try:
        threading.Thread(target=process_single_transition, args=(video_urls,)).start()
        return jsonify({'result': 'Video processing started in the background.'}), 200
    except Exception as e:  
        return jsonify({'result': str(e)}), 400



if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=8000)