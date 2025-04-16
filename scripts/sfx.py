# scripts/sfx.py

import json
import os
import re
import time
import shutil
import logging
import numpy as np
from moviepy.editor import (
    ImageClip, 
    concatenate_videoclips, 
    AudioFileClip, 
    CompositeAudioClip,
    concatenate_audioclips
)
from kokoro import KPipeline
import soundfile as sf
import argparse
import emoji  # Ensure installed: pip install emoji

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Constants
# SFX marker: e.g. [SFX:cough.wav,0.5,1.0]
SFX_PATTERN = re.compile(r'\[SFX:([^\]]+)\]')
AUDIO_DIR = "audio"
VIDEO_DIR = "video"
OUTPUT_VIDEO = "output/final_video.mp4"
CONVERSATION_FILE = "utils/conversation.json"
CONFIG_FILE = "utils/config.json"

# Initialize Kokoro TTS pipeline
pipeline = KPipeline(lang_code='a')

def load_config(config_file=CONFIG_FILE):
    try:
        with open(config_file, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error loading config: {e}")
        return None

def load_conversation(conversation_file=CONVERSATION_FILE):
    try:
        with open(conversation_file, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logging.error(f"Error loading conversation: {e}")
        return None

def remove_emojis(text):
    return emoji.replace_emoji(text, replace='')

def remove_markdown(text):
    return re.sub(r'(\*\*\*|\*\*|\*|~~)', '', text)

def process_text_and_sfx(text):
    matches = list(SFX_PATTERN.finditer(text))
    text_without_sfx = SFX_PATTERN.sub('', text)
    text_no_md = remove_markdown(text_without_sfx)
    cleaned_text = remove_emojis(text_no_md)

    sfx_events = []
    for match in matches:
        substring = text[:match.start()]
        substring_clean = remove_emojis(remove_markdown(SFX_PATTERN.sub('', substring)))
        cleaned_position = len(substring_clean)
        total_length = len(cleaned_text)
        proportion = cleaned_position / total_length if total_length > 0 else 0

        params = match.group(1).split(',')
        sfx_file = params[0].strip()
        additional_offset = float(params[1]) if len(params) > 1 else 0.0
        volume = float(params[2]) if len(params) > 2 else 1.0

        sfx_events.append({
            'file': sfx_file,
            'proportion': proportion,
            'additional_offset': additional_offset,
            'volume': volume
        })
    return cleaned_text, sfx_events

def generate_segment_audio(text, index, voice):
    if not text:
        return None, 0.0

    os.makedirs(AUDIO_DIR, exist_ok=True)
    audio_path = os.path.join(AUDIO_DIR, f"seg_{index}.wav")
    try:
        generator = pipeline(text, voice=voice, split_pattern=r'\n+')
        audio_segments = [audio for _, _, audio in generator]
        if audio_segments:
            combined = np.concatenate(audio_segments)
            sf.write(audio_path, combined, 24000)
            audio_clip = AudioFileClip(audio_path)
            return audio_clip, audio_clip.duration
    except Exception as e:
        logging.error(f"Error generating TTS for segment {index}: {e}")
    return None, 0.0

def process_message(message, index, voice):
    original_text = message.get("text", "")
    base_duration = message.get("duration", 1)
    cleaned_text, sfx_events = process_text_and_sfx(original_text)
    main_audio, duration = generate_segment_audio(cleaned_text, index, voice)

    for event in sfx_events:
        event['start'] = event['proportion'] * duration + event.get('additional_offset', 0.0)

    final_duration = base_duration if main_audio is None else max(base_duration, duration)

    return {
        'index': index,
        'cleaned_text': cleaned_text,
        'duration': final_duration,
        'main_audio': main_audio,
        'sfx_events': sfx_events
    }

def flatten_conversation(conversation):
    config = load_config()
    flat = []
    index = 1

    for entry in conversation.get("conversation", []):
        role = entry.get("role", "unknown")
        user_config = config.get(role, config.get("default", {}))
        voice = user_config.get("voice_model", "af_heart")

        for msg in entry.get("messages", []):
            processed = process_message(msg, index, voice)
            processed['role'] = role
            flat.append(processed)
            index += 1
            time.sleep(0.1)
    return flat

def create_sfx_video(flat_list, output_video=OUTPUT_VIDEO):
    config = load_config()
    background_music_path = config.get("default", {}).get("background_music_path")

    clips = []
    for item in flat_list:
        image_file = os.path.join(VIDEO_DIR, f"message_{item['index']}_{item['role']}.png")
        if not os.path.exists(image_file):
            logging.warning(f"Missing image: {image_file}")
            continue
        clip = ImageClip(image_file).set_duration(item['duration'])
        audio_components = []
        if item['main_audio']:
            audio_components.append(item['main_audio'])
        for sfx in item['sfx_events']:
            sfx_path = os.path.join("sfx", sfx['file'])
            if os.path.exists(sfx_path):
                try:
                    sfx_clip = AudioFileClip(sfx_path)
                    sfx_clip = sfx_clip.volumex(sfx['volume']).set_start(sfx['start'])
                    audio_components.append(sfx_clip)
                except Exception as e:
                    logging.error(f"Error loading SFX {sfx_path}: {e}")
        if audio_components:
            clip = clip.set_audio(CompositeAudioClip(audio_components))
        clips.append(clip)

    if clips:
        video = concatenate_videoclips(clips, method="compose")
        if background_music_path and os.path.exists(background_music_path):
            try:
                bg_music = AudioFileClip(background_music_path).volumex(0.3).set_duration(video.duration)
                final_audio = CompositeAudioClip([video.audio, bg_music]) if video.audio else bg_music
                video = video.set_audio(final_audio)
            except Exception as e:
                logging.warning(f"Failed to apply background music: {e}")
        try:
            video.write_videofile(
                output_video,
                fps=24,
                codec="libx264",
                audio_codec="aac",
                threads=4
            )
            logging.info(f"Successfully created {output_video}")
        except Exception as e:
            logging.error(f"Video render failed: {e}")
    else:
        logging.error("No valid clips to render")

def main():
    parser = argparse.ArgumentParser(description="Create final video with SFX")
    parser.add_argument("--conversation", default=CONVERSATION_FILE)
    parser.add_argument("--output", default=OUTPUT_VIDEO)
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()

    conversation = load_conversation(args.conversation)
    if not conversation:
        return

    flat_list = flatten_conversation(conversation)
    create_sfx_video(flat_list, args.output)

    if args.cleanup:
        for folder in [AUDIO_DIR, VIDEO_DIR]:
            try:
                shutil.rmtree(folder)
                logging.info(f"Cleaned up {folder}")
            except FileNotFoundError:
                pass

if __name__ == "__main__":
    main()
