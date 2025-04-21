# scripts/sfx.py

import json
import os
import time
import shutil
import logging
import argparse
import glob
import emoji
import re
import numpy as np
import soundfile as sf

from moviepy.editor import (
    ImageClip,
    concatenate_videoclips,
    AudioFileClip,
    CompositeAudioClip
)
from kokoro import KPipeline

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

AUDIO_DIR    = "audio"
VIDEO_DIR    = "video"
OUTPUT_VIDEO = "output/final_video.mp4"
CONV_FILE    = "utils/conversation.json"
CONFIG_FILE  = "utils/config.json"

# Kokoro TTS (only for non-system text)
pipeline = KPipeline(lang_code='a')


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading {path}: {e}")
        return {}

def remove_emojis(text):
    return emoji.replace_emoji(text, replace='')

def remove_markdown(text):
    return re.sub(r'(\*\*\*|\*\*|\*|~~)', '', text)

def process_text_and_sfx(msg):
    raw   = msg.get("text","")
    clean = remove_emojis(remove_markdown(raw))

    sfx_evts = []
    raw_sfx = msg.get("sfx", [])
    if isinstance(raw_sfx, dict):
        raw_sfx = [raw_sfx]
    for e in raw_sfx:
        sfx_evts.append({
            "file":   e["file"],
            "offset": float(e.get("offset", 0.0)),
            "volume": float(e.get("volume", 1.0))
        })
    return clean, sfx_evts

def generate_tts(text, idx, voice):
    """Generate a WAV via Kokoro and return (AudioClip, duration)."""
    if not text:
        return None, 0.0
    os.makedirs(AUDIO_DIR, exist_ok=True)
    out = os.path.join(AUDIO_DIR, f"tts_{idx}.wav")
    try:
        gen   = pipeline(text, voice=voice, split_pattern=r'\n+')
        parts = [audio for _, _, audio in gen]
        combined = np.concatenate(parts) if parts else np.zeros(1, dtype=np.float32)
        sf.write(out, combined, 24000)
        clip = AudioFileClip(out)
        return clip, clip.duration
    except Exception as e:
        logging.error(f"TTS error #{idx}: {e}")
        return None, 0.0

def safe_duration(d):
    try:
        return max(0.1, float(d))
    except:
        return 1.0

def flatten_conversation(conv):
    """
    Mirrors your frame‑generator, but now:
    - speaks EVERY non-system text at the frame where it first appears,
    - retains system SFX but skips system TTS,
    - preserves full message+reaction sync.
    """
    cfg  = load_json(CONFIG_FILE)
    default_voice = cfg.get("default", {}).get("voice_model", "af_heart")
    flat = []
    idx  = 1
    for entry in conv.get("conversation", []):
        role     = entry.get("role", "unknown")
        user_cfg = cfg.get(role, cfg.get("default", {}))
        voice    = user_cfg.get("voice_model", default_voice)

        # --- SYSTEM MESSAGES: SFX only, no TTS ---
        if role == "system":
            for msg in entry.get("messages", []):
                _, sys_sfx = process_text_and_sfx(msg)
                dur = safe_duration(msg.get("duration", 1))
                flat.append({
                    "duration":   dur,
                    "tts_clip":   None,
                    "sfx_events": sys_sfx
                })
                idx += 1
            continue

        msgs = entry.get("messages", [])

        # --- PREFIX FRAMES: each message[i] is shown alone on frame i+1 ---
        # now we TTS at that moment
        for i in range(1, len(msgs)):
            m = msgs[i-1]
            clean, msg_sfx = process_text_and_sfx(m)
            tts_clip, tts_dur = generate_tts(clean, idx, voice)
            dur = max(safe_duration(m.get("duration",1)), tts_dur)
            flat.append({
                "duration":   dur,
                "tts_clip":   tts_clip,
                "sfx_events": msg_sfx
            })
            idx += 1

        # --- FULL MESSAGE + REACTIONS: for the last message only ---
        last = msgs[-1] if msgs else {}
        clean, last_sfx = process_text_and_sfx(last)
        tts_clip, tts_dur = generate_tts(clean, idx, voice)
        full_dur = max(safe_duration(last.get("duration",0)), tts_dur)

        reacts = entry.get("reactions", [])
        if reacts:
            for r_i, react in enumerate(reacts):
                evts = []
                # first reaction frame gets the message‐level SFX + TTS
                if r_i == 0:
                    evts.extend(last_sfx)
                raw_r = react.get("sfx", [])
                if isinstance(raw_r, dict):
                    raw_r = [raw_r]
                for e in raw_r:
                    evts.append({
                        "file":   e["file"],
                        "offset": float(e.get("offset",0.0)),
                        "volume": float(e.get("volume",1.0))
                    })
                flat.append({
                    "duration":   full_dur,
                    "tts_clip":   tts_clip if r_i==0 else None,
                    "sfx_events": evts
                })
                idx += 1
        else:
            # no reactions: single frame with TTS + all last‐msg SFX
            flat.append({
                "duration":   full_dur,
                "tts_clip":   tts_clip,
                "sfx_events": last_sfx
            })
            idx += 1

    return flat

def create_sfx_video(flat_list, output=OUTPUT_VIDEO):
    cfg      = load_json(CONFIG_FILE)
    bg_music = cfg.get("default", {}).get("background_music_path")

    frames = sorted(glob.glob(os.path.join(VIDEO_DIR, "*.png")))
    if not frames:
        logging.error("No frames found; aborting."); sys.exit(1)
    if len(frames)!=len(flat_list):
        logging.warning(f"{len(frames)} frames vs {len(flat_list)} audio entries; clipping.")

    clips = []
    cumulative = 0.0
    audio_parts = []

    for frame, entry in zip(frames, flat_list):
        clip = ImageClip(frame).set_duration(entry["duration"])
        clips.append(clip)

        if entry["tts_clip"]:
            audio_parts.append(entry["tts_clip"].set_start(cumulative))

        for s in entry["sfx_events"]:
            path = os.path.join("sfx", s["file"])
            if os.path.exists(path):
                try:
                    sc = (AudioFileClip(path)
                          .volumex(s["volume"])
                          .set_start(cumulative + s["offset"]))
                    audio_parts.append(sc)
                except Exception as e:
                    logging.error(f"SFX load error {path}: {e}")
            else:
                logging.warning(f"Missing SFX: {path}")

        cumulative += entry["duration"]

    final_vid = concatenate_videoclips(clips, method="compose")
    if audio_parts:
        final_vid = final_vid.set_audio(CompositeAudioClip(audio_parts))

    # optional background music
    if bg_music and os.path.exists(bg_music):
        try:
            bg = (AudioFileClip(bg_music)
                  .volumex(0.3)
                  .set_start(0)
                  .set_duration(final_vid.duration))
            final_vid = final_vid.set_audio(CompositeAudioClip([final_vid.audio, bg]))
        except Exception as e:
            logging.warning(f"BG music error: {e}")

    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    try:
        final_vid.write_videofile(output, fps=24, codec="libx264", audio_codec="aac", threads=4)
        logging.info(f"Final video created at {output}")
    except Exception as e:
        logging.error(f"Render failed: {e}")
        sys.exit(1)

def main():
    p = argparse.ArgumentParser("Create final video with all non-system text spoken")
    p.add_argument("--conversation", default=CONV_FILE)
    p.add_argument("--output",       default=OUTPUT_VIDEO)
    p.add_argument("--cleanup",      action="store_true")
    args = p.parse_args()

    conv = load_json(args.conversation)
    flat = flatten_conversation(conv)
    create_sfx_video(flat, args.output)
    if args.cleanup:
        for d in (AUDIO_DIR, VIDEO_DIR):
            shutil.rmtree(d, ignore_errors=True)
            logging.info(f"Removed {d}")

if __name__ == "__main__":
    main()
