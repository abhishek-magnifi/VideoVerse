import os
import subprocess
from flask import Flask, request, jsonify
import time
import threading
import logging
import uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
logging.basicConfig(level=logging.INFO)

def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'mp4', 'avi', 'mkv', 'mov', 'flv'}

def _delete_uploaded_videos(video_paths):
    for video_path in video_paths:
        try:
            os.remove(video_path)
        except Exception as e:
            logging.error(f"Error deleting file '{video_path}': {e}")

def add_transition(video_paths):
    start = time.time()
    video_durations = []
    video_file_name = f'transition_video_{uuid.uuid4()}.mp4'

    try:
        ffmpeg_command = ['ffmpeg'] 
        for video_path in video_paths:
            ffprobe_command = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', video_path]
            duration = int(float(subprocess.check_output(ffprobe_command).decode('utf-8').strip()))
            video_durations.append(duration)
            ffmpeg_command.extend(['-i', video_path])
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
        ffmpeg_command.extend(['-filter_complex', filter_complex] + mapping_options + ['-c:v', 'libx264', '-preset', 'fast', '-crf', '30', '-c:a', 'aac', '-strict', 'experimental', '-shortest', '-y'] +[f'ffmpegapp/{video_file_name}'])
        print(ffmpeg_command)
        subprocess.run(ffmpeg_command, capture_output=True, text=True, check=True)
        end = time.time()
        print(f"Transition video created: '{video_file_name}'")

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise

    finally:
        print("Total_time: ", end-start)
        _delete_uploaded_videos(video_paths=video_paths)


def add_audio_overlay(video_files, sound_overlay, sound_volume_percentage, transition_bool):

    start = time.time()
    video_durations = []
    video_file_name = f'transition_video_{uuid.uuid4()}.mp4'
    final_video_file_name = f'output_video_{uuid.uuid4()}.mp4'
    new_command = ['ffmpeg','-i', f'ffmpegapp/{video_file_name}']

    try:
        ffmpeg_command = ['ffmpeg']
        if transition_bool.lower() == 'true':

            for video_url in video_files:
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
            ffmpeg_command.extend(['-filter_complex', filter_complex] + mapping_options + ['-c:v', 'libx264', '-preset', 'fast', '-crf', '30', '-c:a', 'aac', '-strict', 'experimental', '-shortest', '-y'] +[f'ffmpegapp/{video_file_name}'])

            start4 = time.time()
            subprocess.run(ffmpeg_command, capture_output=True, text=True, check=True)
            new_command.extend([
                '-i',
                sound_overlay,
                '-filter_complex',
                f'[0:a]volume=1.0[a0];[1:a]volume={int(sound_volume_percentage)/100}[a1];[a0][a1]amix=inputs=2:duration=shortest',
                '-c:v',
                'copy',
                f'ffmpegapp/{final_video_file_name}'])

            subprocess.run(new_command, capture_output=True, text=True, check=True)
            os.remove(f'ffmpegapp/{video_file_name}')
            end = time.time()
            print(f"Transition video created: '{final_video_file_name}'")

        else:

            filter_complex = ''

            for i,video_url in enumerate(video_files):
                ffmpeg_command.extend(['-i', video_url])
                filter_complex += f'[{i}:v]'
                if i == len(video_files) - 1:
                    filter_complex += f'concat=n={len(video_files)}:v=1:a=0[vout];'

            for i,path in enumerate(video_files):
                filter_complex += f'[{i}:a]'
                if i == len(video_files) - 1:
                    filter_complex += f'concat=n={len(video_files)}:v=0:a=1[aout]'
    
            ffmpeg_command.extend(['-filter_complex', filter_complex, '-map', '[vout]', '-map', '[aout]', '-c:v', 'libx264', '-preset', 'fast', '-crf', '30', '-c:a', 'aac', '-strict', 'experimental', '-shortest', '-y', f'ffmpegapp/{video_file_name}'])
            print(ffmpeg_command)
            subprocess.run(ffmpeg_command, capture_output=True, text=True, check=True)

            new_command.extend([
                '-i',
                f'{sound_overlay}',
                '-filter_complex',
                f'[0:a]volume=1.0[a0];[1:a]volume={int(sound_volume_percentage)/100}[a1];[a0][a1]amix=inputs=2:duration=first',
                '-c:v',
                'copy',
                f'ffmpegapp/{final_video_file_name}'
                ])
            print(new_command)
            os.remove(f'ffmpegapp/{video_file_name}')
            end = time.time()
            print(f"Merged video created: '{final_video_file_name}'")

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise e

    finally:
        print("Total_time: ", end-start)


def add_transition_new_trim(video_paths):
    start = time.time()
    video_durations = []
    video_file_name = f'transition_video_{uuid.uuid4()}.mp4'
    duration_table = {}

    try:
        ffmpeg_command = ['ffmpeg']
        mapping_options = []
        video_filter_parts = []
        audio_filter_parts = []
        video_transition_part = []
        audio_transition_part = []
        concat_video_filter_part = ''
        concat_audio_filter_part = ''

        for video_path in video_paths:
            ffprobe_command = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', video_path]
            duration = int(float(subprocess.check_output(ffprobe_command).decode('utf-8').strip()))
            duration_table[video_path] = duration
            ffmpeg_command.extend(['-i', video_path])

        for idx, (key, value) in enumerate(duration_table.items()):
            
            if idx == 0:
                video_filter_parts.append(f'[{idx}:v]trim=end={value-3},setpts=PTS-STARTPTS[split_{idx}]')
                video_filter_parts.append(f'[{idx}:v]trim=start={value-3},setpts=PTS-STARTPTS[merging_split_{idx}]')
                audio_filter_parts.append(f'[{idx}:a]atrim=end={value-3},asetpts=PTS-STARTPTS[split_audio_{idx}]')
                audio_filter_parts.append(f'[{idx}:a]atrim=start={value-3},asetpts=PTS-STARTPTS[merging_split_audio_{idx}]')
                
            elif idx < len(duration_table):
                video_filter_parts.append(f'[{idx}:v]trim=end=3,setpts=PTS-STARTPTS[merging_split_{idx}_0]')
                video_filter_parts.append(f'[{idx}:v]trim=start=3,setpts=PTS-STARTPTS[split_{idx}]')
                video_filter_parts.append(f'[{idx}:v]trim=start={value-3},setpts=PTS-STARTPTS[merging_split_{idx}_1]')
                audio_filter_parts.append(f'[{idx}:a]atrim=end=3,asetpts=PTS-STARTPTS[merging_split_audio_{idx}_0]')
                audio_filter_parts.append(f'[{idx}:a]atrim=start=3,asetpts=PTS-STARTPTS[split_audio_{idx}]')
                audio_filter_parts.append(f'[{idx}:a]atrim=start={value-3},asetpts=PTS-STARTPTS[merging_split_audio_{idx}_1]')

            if idx == 0:
                video_transition_part.extend([f'[merging_split_{idx}][merging_split_{idx+1}_0]xfade=transition=fade:duration=1:offset=1,format=yuv420p[transition_v{idx}]'])
                audio_transition_part.extend([f'[merging_split_audio_{idx}][merging_split_audio_{idx+1}_0]acrossfade=d=2[transition_a{idx}]'])

            elif idx < len(duration_table)-1:
                video_transition_part.extend([f'[merging_split_{idx}_1][merging_split_{idx+1}_0]xfade=transition=fade:duration=1:offset=1,format=yuv420p[transition_v{idx}]'])
                audio_transition_part.extend([f'[merging_split_audio_{idx}_1][merging_split_audio_{idx+1}_0]acrossfade=d=2[transition_a{idx}]'])
                
            if idx < len(duration_table)-1: 
                concat_video_filter_part += (f'[split_{idx}][transition_v{idx}]')
                concat_audio_filter_part += (f'[split_audio_{idx}][transition_a{idx}]')

            elif idx == len(duration_table)-1:
                concat_video_filter_part += (f'[split_{idx}][merging_split_{idx}_1]concat=n={2*len(duration_table)}:v=1:a=0[vout];')
                concat_audio_filter_part += (f'[split_audio_{idx}][merging_split_audio_{idx}_1]concat=n={2*len(duration_table)}:v=0:a=1[aout]')

            mapping_options = ['-map', '[vout]', '-map', '[aout]']

        video_filter_complex = ';'.join(video_filter_parts)
        audio_filter_complex = ';'.join(audio_filter_parts)
        video_transition_complex = ';'.join(video_transition_part)
        audio_transition_complex = ';'.join(audio_transition_part)

        filter_complex = f'{video_filter_complex};{video_transition_complex};{audio_filter_complex};{audio_transition_complex};{concat_video_filter_part}{concat_audio_filter_part}'
        ffmpeg_command.extend(['-filter_complex', filter_complex] + mapping_options + ['-c:v', 'libx264', '-preset', 'medium', '-crf', '25', '-c:a', 'aac', '-strict', 'experimental', '-shortest', '-y'] +[f'ffmpegapp/{video_file_name}'])
        print(ffmpeg_command)
        a = subprocess.run(ffmpeg_command, capture_output=True)

        print(f"Transition video created: '{video_file_name}'")

    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise

    finally:
        end = time.time()
        print("Total_time: ", end-start)
        # _delete_uploaded_videos(video_paths=video_paths)

def live_stream_chunking(video_paths):
    start = time.time()
    video_durations = []
    video_file_name = f'transition_video_{uuid.uuid4()}.mp4'
    duration_table = {}

    try:
        ffmpeg_command = ['ffmpeg']
        mapping_options = []
        video_filter_parts = []
        audio_filter_parts = []
        video_transition_part = []
        audio_transition_part = []
        concat_video_filter_part = ''
        concat_audio_filter_part = ''

        for video_path in video_paths:
            ffprobe_command = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', video_path]
            duration = int(float(subprocess.check_output(ffprobe_command).decode('utf-8').strip()))
            duration_table[video_path] = duration
            ffmpeg_command.extend(['-i', video_path])

        for idx, (key, value) in enumerate(duration_table.items()):
            
            if idx == 0:
                video_filter_parts.append(f'[{idx}:v]trim=end={value-3},setpts=PTS-STARTPTS[split_{idx}]')
                video_filter_parts.append(f'[{idx}:v]trim=start={value-3},setpts=PTS-STARTPTS[merging_split_{idx}]')
                audio_filter_parts.append(f'[{idx}:a]atrim=end={value-3},asetpts=PTS-STARTPTS[split_audio_{idx}]')
                audio_filter_parts.append(f'[{idx}:a]atrim=start={value-3},asetpts=PTS-STARTPTS[merging_split_audio_{idx}]')

            elif idx < len(duration_table):
                video_filter_parts.append(f'[{idx}:v]trim=end=3,setpts=PTS-STARTPTS[merging_split_{idx}_0]')
                video_filter_parts.append(f'[{idx}:v]trim=start=3,setpts=PTS-STARTPTS[split_{idx}]')
                video_filter_parts.append(f'[{idx}:v]trim=start={value-3},setpts=PTS-STARTPTS[merging_split_{idx}_1]')
                audio_filter_parts.append(f'[{idx}:a]atrim=end=3,asetpts=PTS-STARTPTS[merging_split_audio_{idx}_0]')
                audio_filter_parts.append(f'[{idx}:a]atrim=start=3,asetpts=PTS-STARTPTS[split_audio_{idx}]')
                audio_filter_parts.append(f'[{idx}:a]atrim=start={value-3},asetpts=PTS-STARTPTS[merging_split_audio_{idx}_1]')

            if idx == 0:
                video_transition_part.extend([f'[merging_split_{idx}][merging_split_{idx+1}_0]xfade=transition=fade:duration=1:offset=1,format=yuv420p[transition_v{idx}]'])
                audio_transition_part.extend([f'[merging_split_audio_{idx}][merging_split_audio_{idx+1}_0]acrossfade=d=2[transition_a{idx}]'])

            elif idx < len(duration_table)-1:
                video_transition_part.extend([f'[merging_split_{idx}_1][merging_split_{idx+1}_0]xfade=transition=fade:duration=1:offset=1,format=yuv420p[transition_v{idx}]'])
                audio_transition_part.extend([f'[merging_split_audio_{idx}_1][merging_split_audio_{idx+1}_0]acrossfade=d=2[transition_a{idx}]'])
  
            if idx < len(duration_table)-1: 
                concat_video_filter_part += (f'[split_{idx}][transition_v{idx}]')
                concat_audio_filter_part += (f'[split_audio_{idx}][transition_a{idx}]')

            elif idx == len(duration_table)-1:
                concat_video_filter_part += (f'[split_{idx}][merging_split_{idx}_1]concat=n={2*len(duration_table)}:v=1:a=0[vout];')
                concat_audio_filter_part += (f'[split_audio_{idx}][merging_split_audio_{idx}_1]concat=n={2*len(duration_table)}:v=0:a=1[aout]')

            mapping_options = ['-map', '[vout]', '-map', '[aout]']

        video_filter_complex = ';'.join(video_filter_parts)
        audio_filter_complex = ';'.join(audio_filter_parts)
        video_transition_complex = ';'.join(video_transition_part)
        audio_transition_complex = ';'.join(audio_transition_part)

        filter_complex = f'{video_filter_complex};{video_transition_complex};{audio_filter_complex};{audio_transition_complex};{concat_video_filter_part}{concat_audio_filter_part}'
        ffmpeg_command.extend(['-filter_complex', filter_complex] + mapping_options + ['-c:v', 'libx264', '-preset', 'medium', '-crf', '25', '-c:a', 'aac', '-strict', 'experimental', '-shortest', '-y'] +[f'ffmpegapp/{video_file_name}'])
        print(ffmpeg_command)
        print("\nSubprocess is running...")
        a = subprocess.run(ffmpeg_command, capture_output=True)
        print("TS part start")

        ffmpeg_command = [
                'ffmpeg',
                '-i', f"ffmpegapp/{video_file_name}",
                '-c:v', 'libx264',
                '-c:a', 'aac',
                '-keyint_min', '5',
                '-sc_threshold', '0',
                '-start_number', '0',
                '-hls_time', '30',
                '-hls_flags', 'independent_segments',
                '-b:v:0', '800k', '-filter:v:0', 'scale=640:360',
                '-b:v:1', '1200k', '-filter:v:1', 'scale=842:480',
                '-b:v:2', '2400k', '-filter:v:2', 'scale=1280:720',
                '-b:v:3', '4800k', '-filter:v:3', 'scale=1920:1080',
                '-map', '0:v', '-map', '0:v', '-map', '0:v', '-map', '0:v',
                '-map', '0:a', '-map', '0:a', '-map', '0:a', '-map', '0:a',
                '-f', 'hls',
                '-var_stream_map', 'v:0,a:0 v:1,a:1 v:2,a:2 v:3,a:3',
                '-master_pl_name', 'master.m3u8',
                '-hls_segment_filename', 'stream_%v/data%03d.ts',
                '-use_localtime_mkdir', '1',
                'stream_%v.m3u8'
            ]

        b = subprocess.run(ffmpeg_command, capture_output=True, text=True)
        print(b.stderr)

        print("TS part end")
        print(f"Transition video created: '{video_file_name}'")
    except Exception as e:
        logging.error(f"An error occurred: {e}")
        raise

    finally:
        end = time.time()
        print("Total_time: ", end-start)
        _delete_uploaded_videos(video_paths=video_paths)


@app.route('/transition', methods=['POST'])
def upload():

    if 'video' not in request.files:
        return jsonify({'error': 'No video file uploaded.'}), 400

    video_files = request.files.getlist('video')
    video_paths = []

    if not all(_allowed_file(file.filename) for file in video_files):
        return jsonify({'error': 'Invalid file format. Supported formats are: mp4, avi, mkv, mov, flv.'}), 400

    try:
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        for video_file in video_files:
            filename = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(video_file.filename))
            video_file.save(filename)
            video_paths.append(filename)

        threading.Thread(target=add_transition_new_trim, args=(video_paths,)).start()
        return jsonify({'result': 'Video processing started in the background.'}), 200

    except Exception as e:
        return jsonify({'result': str(e)}), 400

@app.route('/add_audio_overlay', methods=['POST'])
def upload_audio():

    data = request.json
    
    if 'video_urls' not in data:
        return jsonify({'error': 'No video file uploaded.'}), 400

    video_files = data['video_urls']
    sound_overlay = data['sound_overlay']
    sound_volume_percentage = data['sound_volume_percentage']
    transition_bool = data['transition_bool']

    try:

        threading.Thread(target=add_audio_overlay, args=(video_files, sound_overlay, sound_volume_percentage, transition_bool,)).start()
        return jsonify({'result': 'Video processing started in the background.'}), 200

    except Exception as e:
        return jsonify({'result': str(e)}), 400

@app.route('/live_stream', methods=['POST'])
def live_stream():

    if 'video' not in request.files:
        return jsonify({'error': 'No video file uploaded.'}), 400

    video_files = request.files.getlist('video')
    video_paths = []

    if not all(_allowed_file(file.filename) for file in video_files):
        return jsonify({'error': 'Invalid file format. Supported formats are: mp4, avi, mkv, mov, flv.'}), 400

    try:
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        for video_file in video_files:
            filename = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(video_file.filename))
            video_file.save(filename)
            video_paths.append(filename)

        threading.Thread(target=live_stream_chunking, args=(video_paths,)).start()
        return jsonify({'result': 'Video processing started in the background.'}), 200

    except Exception as e:
        return jsonify({'result': str(e)}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True, port=8000)