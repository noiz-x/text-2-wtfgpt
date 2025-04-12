# sfx.py

import json
import os
import time
import shutil
import logging
import numpy as np
from moviepy.editor import ImageClip, concatenate_videoclips, AudioFileClip, concatenate_audioclips
from kokoro import KPipeline
import soundfile as sf
import argparse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# Directories and file paths
AUDIO_DIR = "audio"
OUTPUT_DIR = "output"
OUTPUT_VIDEO = "final_video.mp4"
CONVERSATION_FILE = "conversation.json"
# main.py

import curses
import subprocess
import sys
import time

MENU_OPTIONS = [
    "1. Generate Portrait Images from Conversation",
    "2. Create Video from Generated Images (Portrait)",
    "3. Create Final Video with Audio (Portrait)",
    "4. Quit"
]

# Mapping of menu option index to a command list.
# The generate_image script now receives a "--config config.json" flag.
# It is assumed that for portrait mode you have a config.json file 
# with parameters (like block_width, vertical padding, etc.) optimized for 9:16 output.
COMMAND_MAPPING = {
    0: ["python", "generate_image.py", "--config", "config.json"],
    1: ["python", "create_video.py"],
    2: ["python", "sfx.py", "--cleanup"],
}

def run_command(command):
    """Suspend curses, run the command and wait for completion."""
    curses.endwin()  # Temporarily end curses mode so output can be seen.
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"Command {command} failed with error: {e}")
    input("\nPress Enter to return to the main menu...")

def draw_menu(stdscr, selected_index):
    stdscr.clear()
    height, width = stdscr.getmaxyx()
    title = "Portrait Conversation Video Creator"
    stdscr.addstr(1, (width - len(title)) // 2, title, curses.A_BOLD | curses.A_UNDERLINE)
    
    # Draw each menu option centered
    for idx, menu_item in enumerate(MENU_OPTIONS):
        x = (width - len(menu_item)) // 2
        y = 3 + idx
        if idx == selected_index:
            stdscr.attron(curses.A_REVERSE)
            stdscr.addstr(y, x, menu_item)
            stdscr.attroff(curses.A_REVERSE)
        else:
            stdscr.addstr(y, x, menu_item)
    stdscr.refresh()

def curses_menu(stdscr):
    curses.curs_set(0)  # Hide the cursor
    selected_index = 0

    while True:
        draw_menu(stdscr, selected_index)
        key = stdscr.getch()
        
        # Navigate the menu using arrow keys or j/k
        if key in [curses.KEY_UP, ord('k')]:
            selected_index = (selected_index - 1) % len(MENU_OPTIONS)
        elif key in [curses.KEY_DOWN, ord('j')]:
            selected_index = (selected_index + 1) % len(MENU_OPTIONS)
        elif key in [curses.KEY_ENTER, 10, 13]:
            # If "Quit" is selected, exit.
            if selected_index == len(MENU_OPTIONS) - 1:
                break
            else:
                command = COMMAND_MAPPING.get(selected_index)
                if command:
                    run_command(command)
        elif key in [ord('q'), ord('Q')]:
            break

def main():
    try:
        curses.wrapper(curses_menu)
    except Exception as e:
        curses.endwin()
        print(f"Error in curses application: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

# Initialize Kokoro TTS pipeline for American English ('a')
pipeline = KPipeline(lang_code='a')

def load_conversation(conversation_file=CONVERSATION_FILE):
    try:
        with open(conversation_file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Conversation file {conversation_file} not found.")
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing {conversation_file}: {e}")
    return None

def generate_tts_kokoro(text, index, voice="af_heart", speed=1.0):
    """
    Generate TTS audio for a given text message using Kokoro TTS.
    Accumulates audio segments and saves the concatenated audio as a WAV file (24kHz).
    """
    os.makedirs(AUDIO_DIR, exist_ok=True)
    audio_path = os.path.join(AUDIO_DIR, f"tts_{index}.wav")
    audio_segments = []
    try:
        generator = pipeline(text, voice=voice, speed=speed, split_pattern=r'\n+')
        for i, (_, _, audio) in enumerate(generator):
            audio_segments.append(audio)
        if audio_segments:
            combined_audio = np.concatenate(audio_segments)
            sf.write(audio_path, combined_audio, 24000)
            logging.info(f"Saved concatenated audio for message {index} as {audio_path}")
            return audio_path
    except Exception as e:
        logging.error(f"Error generating audio with Kokoro for message {index}: {e}")
    return None

def flatten_conversation(conversation):
    """
    Process conversation messages to produce a flat list of tuples:
    (message index, role, duration, audio_path)
    """
    flat = []
    index = 1
    for entry in conversation.get("conversation", []):
        role = entry.get("role", "unknown")
        voice = "af_heart" if role == "assistant" else "am_adam"
        for msg in entry.get("messages", []):
            text = msg.get("text", "")
            audio_path = generate_tts_kokoro(text, index, voice=voice)
            duration = 1  # fallback duration
            if audio_path:
                try:
                    with AudioFileClip(audio_path) as ac:
                        duration = ac.duration
                        logging.info(f"Audio file {audio_path} duration: {duration} seconds")
                except Exception as e:
                    logging.error(f"Error loading audio {audio_path}: {e}")
            flat.append((index, role, duration, audio_path))
            index += 1
            time.sleep(0.1)  # slight delay between processing messages
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
            logging.warning(f"Image file {image_file} not found. Skipping message {index}.")
            continue
        
        clip = ImageClip(image_file).set_duration(duration)
        clips.append(clip)
        
        if audio_path and os.path.exists(audio_path):
            try:
                ac = AudioFileClip(audio_path)
                logging.info(f"Adding audio for message {index} with duration {ac.duration} seconds")
                audio_clips.append(ac)
            except Exception as e:
                logging.error(f"Error loading audio clip from {audio_path}: {e}")
    
    if not clips:
        logging.error("No valid image clips found. Cannot create video.")
        return
    
    video = concatenate_videoclips(clips, method="compose")
    
    if audio_clips:
        try:
            concatenated_audio = concatenate_audioclips(audio_clips)
            video = video.set_audio(concatenated_audio)
        except Exception as e:
            logging.error("Error concatenating audio clips: " + str(e))
    else:
        logging.warning("No valid audio clips found to add to video.")
    
    try:
        video.write_videofile(output_video, fps=24, codec="libx264", audio_codec="aac")
        logging.info(f"Final video saved as {output_video}")
    except Exception as e:
        logging.error(f"Error during video export: {e}")

def main():
    parser = argparse.ArgumentParser(description="Create final video with audio.")
    parser.add_argument("--conversation", default=CONVERSATION_FILE, help="Path to conversation JSON file.")
    parser.add_argument("--output", default=OUTPUT_VIDEO, help="Output video file name.")
    parser.add_argument("--cleanup", action="store_true", help="Delete intermediate audio and image directories after video creation.")
    args = parser.parse_args()
    
    conversation = load_conversation(args.conversation)
    if not conversation:
        return
    flat_list = flatten_conversation(conversation)
    os.makedirs("output", exist_ok=True)
    create_sfx_video(flat_list, output_video=args.output)
    
    if args.cleanup:
        try:
            if os.path.exists(AUDIO_DIR):
                shutil.rmtree(AUDIO_DIR)
                logging.info("Audio folder deleted.")
            if os.path.exists(OUTPUT_DIR):
                shutil.rmtree(OUTPUT_DIR)
                logging.info("Output folder deleted.")
        except Exception as e:
            logging.error("Error deleting directories: " + str(e))

if __name__ == "__main__":
    main()
