# scripts/create_video.py

import json
import os
import sys
import logging
import argparse
import glob
from moviepy.editor import ImageClip, concatenate_videoclips

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def load_conversation(conversation_file):
    try:
        with open(conversation_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading {conversation_file}: {e}")
        return None


def safe_duration(d):
    try:
        return max(0.1, float(d))
    except:
        return 1.0


def flatten_durations(conversation):
    """
    Walks the JSON exactly as the frame-generator does, emitting one duration
    per frame in strict order.
    """
    durations = []
    for entry in conversation.get("conversation", []):
        role = entry.get("role", "unknown")
        msgs = entry.get("messages", [])

        if role == "system":
            # one frame per system message
            for msg in msgs:
                durations.append(safe_duration(msg.get("duration", 1)))
            continue

        # typing build‑up frames
        for i in range(1, len(msgs)):
            durations.append(safe_duration(msgs[i-1].get("duration", 1)))

        # the “full” message, once per reaction or once if no reactions
        final_dur = safe_duration(msgs[-1].get("duration", 1)) if msgs else 1.0
        reactions = entry.get("reactions", [])
        if reactions:
            for _ in reactions:
                durations.append(final_dur)
        else:
            durations.append(final_dur)

    return durations


def create_video(flat_list, output_video, image_dir):
    os.makedirs(os.path.dirname(output_video) or ".", exist_ok=True)

    # Grab video frames in lexical order (0001.png, 0002.png, …)
    pattern = os.path.join(image_dir, "*.png")
    frames = sorted(glob.glob(pattern))
    if not frames:
        logging.error(f"No frames found in {image_dir}; aborting.")
        sys.exit(1)

    if len(frames) != len(flat_list):
        logging.warning(
            f"Found {len(frames)} frames but {len(flat_list)} durations; "
            "trimming to the shorter list."
        )

    clips = []
    for img_path, dur in zip(frames, flat_list):
        clips.append(ImageClip(img_path).set_duration(dur))

    video = concatenate_videoclips(clips, method="compose")
    try:
        video.write_videofile(output_video, fps=24)
        logging.info(f"Video saved as {output_video}")
    except Exception as e:
        logging.error(f"Failed to write video: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Create video from printed frames.")
    parser.add_argument(
        "--conversation", default="utils/conversation.json",
        help="Path to the conversation JSON."
    )
    parser.add_argument(
        "--image-dir", default="video",
        help="Directory of zero‐padded PNG frames."
    )
    parser.add_argument(
        "--output", default="video/conversation_video.mp4",
        help="Destination for the rendered video."
    )
    args = parser.parse_args()

    conv = load_conversation(args.conversation)
    if not conv:
        sys.exit(1)

    durations = flatten_durations(conv)
    create_video(durations, args.output, args.image_dir)


if __name__ == "__main__":
    main()
