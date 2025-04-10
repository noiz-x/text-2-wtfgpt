# sfx.py

import json
import os
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip

SFX_DIR = "sfx"
VIDEO_PATH = "output/conversation_video.mp4"
OUTPUT_PATH = "output/final_video.mp4"
CONVERSATION_FILE = "conversation.json"

def load_conversation(conversation_file=CONVERSATION_FILE):
    with open(conversation_file, "r") as f:
        return json.load(f)

def flatten_conversation(conversation):
    """
    Flatten the conversation into a list of tuples:
    (image_index, role, duration, sfx_file_path)
    """
    flat = []
    index = 1
    for entry in conversation["conversation"]:
        role = entry["role"]
        for msg in entry["messages"]:
            sfx_file = os.path.join(SFX_DIR, f"{msg['sfx']}.mp3")
            flat.append((index, role, msg["duration"], sfx_file))
            index += 1
    return flat

def create_sfx_video(flat_list, input_video=VIDEO_PATH, output_video=OUTPUT_PATH):
    video_clip = VideoFileClip(input_video)
    audio_clips = []
    current_time = 0.0

    for index, role, duration, sfx_path in flat_list:
        if os.path.exists(sfx_path):
            try:
                sfx_clip = AudioFileClip(sfx_path).set_start(current_time)
                audio_clips.append(sfx_clip)
            except Exception as e:
                print(f"Error loading {sfx_path}: {e}")
        else:
            print(f"Sound effect file {sfx_path} not found.")
        current_time += duration

    if audio_clips:
        composite_audio = CompositeAudioClip(audio_clips)
        final_video = video_clip.set_audio(composite_audio)
        final_video.write_videofile(output_video, fps=24)
    else:
        print("No audio clips found, video will be created without sound.")
        video_clip.write_videofile(output_video, fps=24)

def main():
    conversation = load_conversation()
    flat_list = flatten_conversation(conversation)
    os.makedirs("output", exist_ok=True)
    create_sfx_video(flat_list)

if __name__ == "__main__":
    main()
