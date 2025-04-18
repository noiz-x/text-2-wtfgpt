# scripts/create_video.py

import json
import os
import sys
import logging
import argparse
from moviepy.editor import ImageClip, concatenate_videoclips

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def load_conversation(conversation_file):
    try:
        with open(conversation_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Conversation file {conversation_file} not found.")
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing {conversation_file}: {e}")
    return None


def safe_duration(d):
    try:
        val = float(d)
        return max(0.1, val)
    except Exception:
        return 1.0


def flatten_conversation(conversation):
    flat = []
    idx = 1

    for entry in conversation.get("conversation", []):
        role = entry.get("role", "unknown")
        messages = entry.get("messages", [])

        if role == "system":
            dur = safe_duration(entry.get("duration", 1))
            flat.append((idx, role, dur))
            idx += 1
            continue

        for i in range(1, len(messages)):
            dur = safe_duration(messages[i - 1].get("duration", 1))
            flat.append((idx, role, dur))
            idx += 1

        full_dur = safe_duration(messages[-1].get("duration", 1)) if messages else 1.0
        reactions = entry.get("reactions", [])
        if reactions:
            for _ in reactions:
                flat.append((idx, role, full_dur))
            idx += 1
        else:
            flat.append((idx, role, full_dur))
            idx += 1

    return flat


def create_video(flat_list, output_video, image_pattern):
    os.makedirs(os.path.dirname(output_video) or ".", exist_ok=True)
    clips = []

    for index, role, duration in flat_list:
        if role == "system":
            # Only one frame expected for system messages
            img_path = image_pattern.format(index=index, role=role) + ".png"
            if os.path.exists(img_path):
                clip = ImageClip(img_path).set_duration(duration)
                clips.append(clip)
            else:
                logging.warning(f"Missing image file: {img_path}")
        else:
            # Try multiple reaction frames: _0.png, _1.png, etc.
            i = 0
            found_any = False
            while True:
                img_path = image_pattern.format(index=index, role=role) + f"_{i}.png"
                if os.path.exists(img_path):
                    clip = ImageClip(img_path).set_duration(duration)
                    clips.append(clip)
                    found_any = True
                    i += 1
                else:
                    break
            if not found_any:
                logging.warning(f"Missing image file(s) for: {image_pattern.format(index=index, role=role)}_[0...].png")

    if not clips:
        logging.error(f"No image clips found (checked {len(flat_list)} entries); aborting.")
        sys.exit(1)

    video = concatenate_videoclips(clips, method="compose")
    try:
        video.write_videofile(output_video, fps=24)
        logging.info(f"Video saved as {output_video}")
    except Exception as e:
        logging.error(f"Failed to write video: {e}")
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Create video from generated message images.")
    parser.add_argument(
        "--conversation", default="utils/conversation.json",
        help="Path to conversation JSON file."
    )
    parser.add_argument(
        "--output", default="video/conversation_video.mp4",
        help="Output video file path."
    )
    parser.add_argument(
        "--image-pattern", default="video/message_{index}_{role}",
        help="Python format string for image filename base (excluding suffix)."
    )
    args = parser.parse_args()

    conversation = load_conversation(args.conversation)
    if not conversation:
        sys.exit(1)

    flat_list = flatten_conversation(conversation)
    create_video(flat_list, args.output, args.image_pattern)


if __name__ == "__main__":
    main()
