# scripts/generate_image.py

import json
import os
import logging
import textwrap
from PIL import Image, ImageDraw, ImageFont
from pilmoji import Pilmoji
from pilmoji.source import GoogleEmojiSource
import argparse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

def load_conversation(conversation_file="utils/conversation.json"):
    try:
        with open(conversation_file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Conversation file {conversation_file} not found.")
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing {conversation_file}: {e}")
    return None

def load_config(config_file="utils/config.json"):
    try:
        with open(config_file, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"Config file {config_file} not found.")
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing {config_file}: {e}")
    return None

def generate_text_profile(name, bg_color, text_color, size, font_path):
    profile_img = Image.new("RGBA", (size, size))
    draw = ImageDraw.Draw(profile_img)
    draw.ellipse((0, 0, size, size), fill=bg_color)
    initials = name[:2].upper() if name else "AI"
    try:
        font = ImageFont.truetype(font_path, size // 2)
    except IOError:
        font = ImageFont.load_default()
    text_bbox = draw.textbbox((0, 0), initials, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    x = (size - text_width) // 2
    y = (size - text_height) // 2
    draw.text((x, y), initials, fill=text_color, font=font)
    return profile_img

def generate_chatgpt_message_block(accumulated_messages, role, message_index, config):
    message_text = "\n".join(accumulated_messages)
    background_color = config.get("background_color", "#000000")
    bubble_color = config.get("bubble_color", "#333333")
    text_color = config.get("text_color", "#FFFFFF")
    font_path = config.get("font_path", "arial.ttf")
    font_size = config.get("font_size", 20)
    block_width = config.get("block_width", 600)
    vertical_padding = config.get("vertical_padding", 10)
    horizontal_padding = config.get("horizontal_padding", 10)
    line_spacing = config.get("line_spacing", 4)
    profile_image_path = config.get("profile_image_path", None)
    profile_name = config.get("profile_name", role.title())  # fallback to role name
    profile_size = config.get("profile_size", 50)
    profile_gap = config.get("profile_gap", 10)
    profile_bg = config.get("profile_bg", "#555555")
    profile_text_color = config.get("profile_text_color", "#FFFFFF")
    feedback_padding_top = config.get("feedback_padding_top", 5)
    feedback_padding_bottom = config.get("feedback_padding_bottom", 5)

    try:
        font = ImageFont.truetype(font_path, font_size)
        name_font = ImageFont.truetype(font_path, max(font_size - 4, 12))
    except IOError:
        font = ImageFont.load_default()
        name_font = ImageFont.load_default()

    profile_x = horizontal_padding
    has_profile = profile_image_path or profile_name
    text_start_x = profile_x + profile_size + profile_gap if has_profile else horizontal_padding

    sample_text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    sample_bbox = font.getbbox(sample_text)
    avg_char_width = (sample_bbox[2] - sample_bbox[0]) / len(sample_text)
    max_text_width = block_width - text_start_x - horizontal_padding
    wrap_width = max(1, int(max_text_width // avg_char_width))

    wrapper = textwrap.TextWrapper(width=wrap_width)
    wrapped_text = wrapper.fill(message_text)
    dummy_img = Image.new("RGB", (block_width, 100), background_color)
    dummy_draw = ImageDraw.Draw(dummy_img)
    text_bbox = dummy_draw.multiline_textbbox((0, 0), wrapped_text, font=font, spacing=line_spacing)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]

    name_height = name_font.getbbox("Ag")[3] + 4
    bubble_height = text_height + 2 * vertical_padding
    feedback_height = font.getbbox("Ag")[3]

    content_height = name_height + bubble_height + feedback_padding_top + feedback_height + feedback_padding_bottom
    total_height = max(profile_size + 2 * vertical_padding, content_height + vertical_padding)

    img = Image.new("RGB", (block_width, total_height), background_color)
    draw = ImageDraw.Draw(img)

    if has_profile:
        if profile_image_path and os.path.exists(profile_image_path):
            try:
                profile_img = Image.open(profile_image_path).convert("RGBA")
            except Exception as e:
                logging.warning(f"Error loading profile image from {profile_image_path}: {e}")
                profile_img = generate_text_profile(profile_name, profile_bg, profile_text_color, profile_size, font_path)
        else:
            profile_img = generate_text_profile(profile_name, profile_bg, profile_text_color, profile_size, font_path)
        profile_img = profile_img.resize((profile_size, profile_size))
        mask = Image.new("L", (profile_size, profile_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, profile_size, profile_size), fill=255)
        profile_img.putalpha(mask)
        profile_y = (total_height - profile_size) // 2
        img.paste(profile_img, (profile_x, profile_y), profile_img)

    name_x = text_start_x
    name_y = vertical_padding
    draw.text((name_x, name_y), profile_name, font=name_font, fill="#ffffff")

    bubble_x0 = text_start_x
    bubble_y0 = name_y + name_height + 6
    bubble_x1 = bubble_x0 + text_width + 2 * horizontal_padding
    bubble_y1 = bubble_y0 + bubble_height
    draw.rounded_rectangle([bubble_x0, bubble_y0, bubble_x1, bubble_y1], radius=20, fill=bubble_color)

    text_draw_x = bubble_x0 + horizontal_padding
    text_draw_y = bubble_y0 + vertical_padding
    with Pilmoji(img, source=GoogleEmojiSource) as pilmoji:
        pilmoji.text((text_draw_x, text_draw_y), wrapped_text, font=font, fill=text_color, spacing=line_spacing)

    feedback_text = "👍   👎"
    feedback_font = font
    feedback_width = draw.textlength(feedback_text, font=feedback_font)
    feedback_x = bubble_x1 - feedback_width - horizontal_padding
    feedback_y = bubble_y1 + feedback_padding_top
    draw.text((feedback_x, feedback_y), feedback_text, font=feedback_font, fill="#aaaaaa")

    os.makedirs("video", exist_ok=True)
    image_filename = f"video/message_{message_index}_{role}.png"
    try:
        img.save(image_filename)
        logging.info(f"Saved image for {role} message block {message_index}: {image_filename}")
    except Exception as e:
        logging.error(f"Failed to save image {image_filename}: {e}")
    return img

def main():
    parser = argparse.ArgumentParser(description="Generate images for conversation messages.")
    parser.add_argument("--conversation", default="utils/conversation.json", help="Path to conversation JSON file.")
    parser.add_argument("--config", default="utils/config.json", help="Path to configuration JSON file.")
    args = parser.parse_args()

    conversation = load_conversation(args.conversation)
    if not conversation:
        return
    config = load_config(args.config)
    if not config:
        return

    message_index = 1
    previous_role = None
    accumulated_messages = []

    for entry in conversation.get("conversation", []):
        role = entry.get("role", "unknown")
        speaker_config = config.get(role) or config.get("default")  # 👈 Dynamic role support
        if speaker_config is None:
            logging.error(f"Missing configuration for role: {role}")
            continue
        for msg_obj in entry.get("messages", []):
            text = msg_obj.get("text", "")
            if previous_role is None or role == previous_role:
                accumulated_messages.append(text)
            else:
                accumulated_messages = [text]
            previous_role = role

            generate_chatgpt_message_block(accumulated_messages, role, message_index, speaker_config)
            message_index += 1

if __name__ == "__main__":
    main()
