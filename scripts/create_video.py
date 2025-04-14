# create_video.py

import json
import os
import sys
import logging
from moviepy.editor import ImageClip, concatenate_videoclips
import argparse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def load_conversation(conversation_file="utils/conversation.json"):
    """Load conversation data from the JSON file."""
    try:
        with open(conversation_file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Conversation file {conversation_file} not found.")
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing {conversation_file}: {e}")
    return None

def flatten_conversation(conversation):
    """
    Flatten the conversation into a list of tuples:
    (image_index, role, duration)
    in the same order as images were generated.
    """
    flat = []
    index = 1
    try:
        for entry in conversation["conversation"]:
            role = entry.get("role", "unknown")
            for msg_obj in entry.get("messages", []):
                duration = msg_obj.get("duration", 1)  # default duration if missing
                flat.append((index, role, duration))
                index += 1
    except KeyError as e:
        logging.error(f"Missing key in conversation structure: {e}")
    return flat

def create_video(flat_list, output_video="video/conversation_video.mp4"):
    clips = []
    for index, role, duration in flat_list:
        filename = f"video/message_{index}_{role}.png"
        if os.path.exists(filename):
            clip = ImageClip(filename).set_duration(duration)
            clips.append(clip)
        else:
            logging.warning(f"{filename} not found.")
    if clips:
        video = concatenate_videoclips(clips, method="compose")
        try:
            video.write_videofile(output_video, fps=24)
            logging.info(f"Video saved as {output_video}")
        except Exception as e:
            logging.error(f"Failed to write video: {e}")
    else:
        logging.error("No clips found to create video.")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Create video from image clips.")
    parser.add_argument("--conversation", default="utils/conversation.json", help="Path to conversation JSON file.")
    parser.add_argument("--output", default="video/conversation_video.mp4", help="Output video file name.")
    args = parser.parse_args()
    
    conversation = load_conversation(args.conversation)
    if not conversation:
        sys.exit(1)
    flat_list = flatten_conversation(conversation)
    os.makedirs("output", exist_ok=True)
    create_video(flat_list, output_video=args.output)

if __name__ == "__main__":
    main()
