# create_video.py

import json
import os
from moviepy.editor import ImageClip, concatenate_videoclips

def load_conversation(conversation_file="conversation.json"):
    """Load conversation data from the JSON file."""
    with open(conversation_file, "r") as f:
        return json.load(f)

def flatten_conversation(conversation):
    """
    Flatten the conversation into a list of tuples:
    (image_index, role, duration)
    in the same order as images were generated.
    """
    flat = []
    index = 1
    for entry in conversation["conversation"]:
        role = entry["role"]
        for msg_obj in entry["messages"]:
            # Each message object has a duration.
            flat.append((index, role, msg_obj["duration"]))
            index += 1
    return flat

def create_video(flat_list, output_video="output/conversation_video.mp4"):
    clips = []
    for index, role, duration in flat_list:
        filename = f"output/message_{index}_{role}.png"
        if os.path.exists(filename):
            clip = ImageClip(filename).set_duration(duration)
            clips.append(clip)
        else:
            print(f"Warning: {filename} not found.")
    if clips:
        video = concatenate_videoclips(clips, method="compose")
        video.write_videofile(output_video, fps=24)
    else:
        print("No clips found to create video.")

def main():
    conversation = load_conversation()
    flat_list = flatten_conversation(conversation)
    os.makedirs("output", exist_ok=True)
    create_video(flat_list)

if __name__ == "__main__":
    main()
