# sfx.py

import json
import os
import time
import shutil
from moviepy.editor import ImageClip, concatenate_videoclips, AudioFileClip, concatenate_audioclips
from kokoro import KPipeline
import soundfile as sf

# Directories and file paths
AUDIO_DIR = "audio"
OUTPUT_DIR = "output"
OUTPUT_VIDEO = "final_video.mp4"
CONVERSATION_FILE = "conversation.json"

# Initialize Kokoro TTS pipeline for American English ('a')
pipeline = KPipeline(lang_code='a')

def load_conversation(conversation_file=CONVERSATION_FILE):
    with open(conversation_file, "r") as f:
        return json.load(f)

def generate_tts_kokoro(text, index, voice="af_heart", speed=1.0):
    """
    Generate TTS audio for a given text message using Kokoro TTS.
    Saves the audio as a WAV file (24kHz) and returns the file path.
    """
    os.makedirs(AUDIO_DIR, exist_ok=True)
    audio_path = os.path.join(AUDIO_DIR, f"tts_{index}.wav")
    try:
        # Pipeline returns a generator yielding (graph, phonemes, audio data)
        generator = pipeline(text, voice=voice, speed=speed, split_pattern=r'\n+')
        for i, (gs, ps, audio) in enumerate(generator):
            sf.write(audio_path, audio, 24000)  # Save as WAV at 24kHz
            print(f"Saved audio for message {index} as {audio_path} (split {i})")
            return audio_path
    except Exception as e:
        print(f"Error generating audio with Kokoro for message {index}: {e}")
        return None

def flatten_conversation(conversation):
    """
    Process conversation messages to produce a flat list of tuples:
    (message index, role, duration, audio_path)
    """
    flat = []
    index = 1
    for entry in conversation["conversation"]:
        role = entry["role"]
        # Choose voice based on role: assistant gets 'af_heart', user gets 'am_adam'
        voice = "af_heart" if role == "assistant" else "am_adam"
        for msg in entry["messages"]:
            text = msg["text"]
            audio_path = generate_tts_kokoro(text, index, voice=voice)
            duration = 1  # fallback duration
            if audio_path:
                try:
                    with AudioFileClip(audio_path) as ac:
                        duration = ac.duration
                        print(f"Audio file {audio_path} duration: {duration} seconds")
                except Exception as e:
                    print(f"Error loading audio {audio_path}: {e}")
            flat.append((index, role, duration, audio_path))
            index += 1
            time.sleep(0.1)  # slight delay
    return flat

def create_sfx_video(flat_list, output_video=OUTPUT_VIDEO):
    """
    Create the final video by combining image clips (generated earlier) 
    with the corresponding TTS audio files.
    Expects image files named "output/message_{index}_{role}.png".
    """
    clips = []
    audio_clips = []
    
    for (index, role, duration, audio_path) in flat_list:
        image_file = f"output/message_{index}_{role}.png"
        if not os.path.exists(image_file):
            print(f"Warning: Image file {image_file} not found. Skipping message {index}.")
            continue
        
        clip = ImageClip(image_file).set_duration(duration)
        clips.append(clip)
        
        if audio_path and os.path.exists(audio_path):
            try:
                ac = AudioFileClip(audio_path)
                print(f"Adding audio for message {index} with duration {ac.duration} seconds")
                audio_clips.append(ac)
            except Exception as e:
                print(f"Error loading audio clip from {audio_path}: {e}")
    
    if not clips:
        print("No valid image clips found. Cannot create video.")
        return
    
    # Concatenate image clips to form video
    video = concatenate_videoclips(clips, method="compose")
    
    # Concatenate audio clips sequentially and set as video audio
    if audio_clips:
        try:
            concatenated_audio = concatenate_audioclips(audio_clips)
            video = video.set_audio(concatenated_audio)
        except Exception as e:
            print("Error concatenating audio clips:", e)
    else:
        print("No valid audio clips found to add to video.")
    
    # Export the final video with specified codecs
    try:
        video.write_videofile(output_video, fps=24, codec="libx264", audio_codec="aac")
    except Exception as e:
        print("Error during video export:", e)

def main():
    conversation = load_conversation()
    flat_list = flatten_conversation(conversation)
    os.makedirs("output", exist_ok=True)
    create_sfx_video(flat_list)
    
    # Delete the audio directory after successful video compilation
    try:
        if os.path.exists(AUDIO_DIR) or os.path.exists(OUTPUT_DIR):
            shutil.rmtree(AUDIO_DIR)
            print("Audio folder deleted.")
            shutil.rmtree(OUTPUT_DIR)
            print("Output folder deleted.")
    except Exception as e:
        print("Error deleting audio folder:", e)

if __name__ == "__main__":
    main()
