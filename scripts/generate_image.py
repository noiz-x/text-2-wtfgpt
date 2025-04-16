# scripts/generate_image.py

import json
import os
import re
import logging
import sys
import argparse
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pilmoji import Pilmoji
from pilmoji.source import GoogleEmojiSource

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# === Utility Functions for Markdown Parsing ===

def parse_markdown(text):
    pattern = re.compile(r'(\*\*\*.*?\*\*\*|\*\*.*?\*\*|\*.*?\*|~~.*?~~)')
    tokens = []
    last_idx = 0
    for match in pattern.finditer(text):
        if match.start() > last_idx:
            tokens.append({
                "text": text[last_idx:match.start()],
                "bold": False,
                "italic": False,
                "strikethrough": False
            })
        token_text = match.group(0)
        if token_text.startswith("***") and token_text.endswith("***"):
            tokens.append({
                "text": token_text[3:-3],
                "bold": True,
                "italic": True,
                "strikethrough": False
            })
        elif token_text.startswith("**") and token_text.endswith("**"):
            tokens.append({
                "text": token_text[2:-2],
                "bold": True,
                "italic": False,
                "strikethrough": False
            })
        elif token_text.startswith("*") and token_text.endswith("*"):
            tokens.append({
                "text": token_text[1:-1],
                "bold": False,
                "italic": True,
                "strikethrough": False
            })
        elif token_text.startswith("~~") and token_text.endswith("~~"):
            tokens.append({
                "text": token_text[2:-2],
                "bold": False,
                "italic": False,
                "strikethrough": True
            })
        last_idx = match.end()
    if last_idx < len(text):
        tokens.append({
            "text": text[last_idx:],
            "bold": False,
            "italic": False,
            "strikethrough": False
        })
    return tokens

def select_font(token, fonts):
    if token["bold"] and token["italic"]:
        return fonts.get("bold_italic", fonts["normal"])
    elif token["bold"]:
        return fonts.get("bold", fonts["normal"])
    elif token["italic"]:
        return fonts.get("italic", fonts["normal"])
    else:
        return fonts["normal"]

def custom_textlength(draw, text, font, emoji_adjustment_factor=1.5):
    total = 0
    emoji_pattern = re.compile(
        "[" 
        "\U0001F300-\U0001F5FF"
        "\U0001F600-\U0001F64F"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "]+", 
        flags=re.UNICODE
    )
    for char in text:
        if emoji_pattern.match(char):
            char_width = font.getmask(char).size[0]
            total += char_width * emoji_adjustment_factor
        else:
            bbox = draw.textbbox((0, 0), char, font=font)
            char_width = (bbox[2] - bbox[0]) if bbox else 0
            total += char_width
    return total

def wrap_tokens(tokens, draw, fonts, max_width):
    lines = []
    current_line = []
    current_width = 0

    for token in tokens:
        words = token["text"].split(" ")
        for i, word in enumerate(words):
            word_text = word + (" " if i < len(words)-1 else "")
            word_text = word_text.replace("\n", " ")
            ttoken = {
                "text": word_text,
                "bold": token["bold"],
                "italic": token["italic"],
                "strikethrough": token["strikethrough"]
            }
            font_used = select_font(ttoken, fonts)
            word_width = custom_textlength(draw, ttoken["text"], font_used)
            if current_line and current_width + word_width > max_width:
                lines.append(current_line)
                current_line = []
                current_width = 0
            current_line.append(ttoken)
            current_width += word_width
    if current_line:
        lines.append(current_line)
    return lines

def draw_markdown_lines(draw, pilmoji, lines, start_x, start_y, line_spacing, fill, fonts):
    y = start_y
    for line in lines:
        x = start_x
        max_line_height = 0
        for token in line:
            token_font = select_font(token, fonts)
            pilmoji.text((x, y), token["text"], font=token_font, fill=fill)
            bbox = draw.textbbox((0, 0), token["text"], font=token_font)
            token_width = bbox[2] - bbox[0]
            token_height = bbox[3] - bbox[1]
            if token["strikethrough"]:
                strike_y = y + token_height
                draw.line((x, strike_y, x + token_width, strike_y), fill=fill, width=1)
            x += token_width
            max_line_height = max(max_line_height, token_height)
        y += max_line_height + line_spacing
    total_height = y - start_y
    return total_height

# === End Markdown Utility Functions ===

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

def generate_text_profile(name, bg_color, text_color, size, font_path, corner_radius_ratio=0.2):
    if not name:
        return None

    scale_factor = 4
    high_res_size = size * scale_factor

    profile_img_high = Image.new("RGBA", (high_res_size, high_res_size))
    draw = ImageDraw.Draw(profile_img_high)
    
    corner_radius = int(high_res_size * corner_radius_ratio)
    draw.rounded_rectangle((0, 0, high_res_size, high_res_size),
                           radius=corner_radius,
                           fill=bg_color)
    
    initials = name[:2].upper()
    
    try:
        font = ImageFont.truetype(font_path, high_res_size // 2)
    except IOError:
        font = ImageFont.load_default()
    
    bbox = draw.textbbox((0, 0), initials, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (high_res_size - text_width) // 2
    y = (high_res_size - text_height) // 2
    draw.text((x, y), initials, fill=text_color, font=font)
    
    profile_img = profile_img_high.resize((size, size), Image.LANCZOS)
    return profile_img

def generate_avatar_from_image(profpic_file, target_width):
    scale_factor = 4
    high_res_target = target_width * scale_factor

    prof_pic = Image.open(profpic_file).convert("RGBA")
    prof_pic.thumbnail((sys.maxsize, high_res_target), Image.LANCZOS)
    
    w, h = prof_pic.size
    diameter = min(w, h)
    left = (w - diameter) // 2
    top = (h - diameter) // 2
    prof_pic = prof_pic.crop((left, top, left + diameter, top + diameter))
    
    high_res_mask = Image.new("L", (diameter, diameter), 0)
    mask_draw = ImageDraw.Draw(high_res_mask)
    mask_draw.ellipse([(0, 0), (diameter, diameter)], fill=255)
    prof_pic.putalpha(high_res_mask)
    
    avatar = prof_pic.resize((target_width, target_width), Image.LANCZOS)
    return avatar

def generate_message_block(accumulated_messages, role, message_index, config):
    # Message content cleanup.
    message_text = "\n".join(msg.strip() for msg in accumulated_messages)
    cleaned_message_text = re.sub(r'\[SFX:[^\]]+\]', '', message_text)

    # Theme colors.
    bg_color = config.get("background_color", "#343541")
    text_color = config.get("text_color", "#e0e0e0")
    username_color = config.get("username_color", "#ffffff")
    
    # Use the current time for the timestamp.
    timestamp = "Today at " + datetime.now().strftime("%-I:%M %p")
  # e.g., "4:20 PM"
    
    font_path = config.get("font_path")
    font_size = config.get("font_size", 24)
    bold_font_path = config.get("bold_font_path", font_path)

    block_width = config.get("block_width", 900)
    avatar_size = config.get("profile_size", 80)
    padding_x = config.get("horizontal_padding", 20)
    padding_y = config.get("vertical_padding", 20)
    gap_between_avatar_and_text = config.get("profile_gap", 20)
    line_spacing = config.get("line_spacing", 8)

    profile_image_path = config.get("profile_image_path")
    profile_name = config.get("profile_name", "Unknown")

    try:
        font = ImageFont.truetype(font_path, font_size)
        bold_font = ImageFont.truetype(bold_font_path, font_size)
        timestamp_font = ImageFont.truetype(font_path, font_size - 6)
    except Exception:
        font = ImageFont.load_default()
        bold_font = font
        timestamp_font = font

    avatar_x = padding_x
    text_start_x = avatar_x + avatar_size + gap_between_avatar_and_text
    max_text_width = block_width - text_start_x - padding_x

    dummy_img = Image.new("RGB", (block_width, 100), bg_color)
    dummy_draw = ImageDraw.Draw(dummy_img)
    tokens = parse_markdown(cleaned_message_text)
    lines_tokens = wrap_tokens(tokens, dummy_draw, {
        "normal": font, "bold": bold_font, "italic": font, "bold_italic": bold_font
    }, max_text_width)

    line_height = dummy_draw.textbbox((0, 0), "Ag", font=font)[3]
    total_text_height = (line_height + line_spacing) * len(lines_tokens)
    username_height = bold_font.getbbox("Ag")[3]
    total_height = max(avatar_size + 2 * padding_y, username_height + total_text_height + 2 * padding_y)

    img = Image.new("RGBA", (block_width, total_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    corner_radius = 8
    draw.rounded_rectangle((0, 0, block_width, total_height), radius=corner_radius, fill=bg_color)

    if profile_image_path and os.path.exists(profile_image_path):
        try:
            avatar = generate_avatar_from_image(profile_image_path, avatar_size)
        except Exception as e:
            logging.error(f"Error processing profile image: {e}")
            avatar = generate_text_profile(profile_name, "#7289da", "#ffffff", avatar_size, font_path)
    else:
        avatar = generate_text_profile(profile_name, "#7289da", "#ffffff", avatar_size, font_path)

    # Create an anti-aliased avatar border using high-res processing.
    hr_avatar_size = avatar_size * 4
    avatar_with_border_hr = Image.new("RGBA", (hr_avatar_size, hr_avatar_size), (0, 0, 0, 0))
    bd = ImageDraw.Draw(avatar_with_border_hr)
    border_width_hr = max(2, hr_avatar_size // 40)
    bd.ellipse((0, 0, hr_avatar_size, hr_avatar_size), fill="#ffffff")
    inner_mask_hr = Image.new("L", (hr_avatar_size, hr_avatar_size), 0)
    ImageDraw.Draw(inner_mask_hr).ellipse((border_width_hr, border_width_hr, hr_avatar_size - border_width_hr, hr_avatar_size - border_width_hr), fill=255)
    avatar_hr = avatar.resize((hr_avatar_size, hr_avatar_size), Image.LANCZOS)
    avatar_with_border_hr.paste(avatar_hr, (0, 0), mask=inner_mask_hr)
    avatar_with_border = avatar_with_border_hr.resize((avatar_size, avatar_size), Image.LANCZOS)
    img.paste(avatar_with_border, (avatar_x, padding_y), avatar_with_border)

    name_y = padding_y
    draw.text((text_start_x, name_y), profile_name, font=bold_font, fill=username_color)
    name_width = draw.textlength(profile_name, font=bold_font)
    draw.text((text_start_x + name_width + 8, name_y + 2), timestamp, font=timestamp_font, fill="gray")

    text_y = name_y + username_height + 4
    with Pilmoji(img, source=GoogleEmojiSource) as pilmoji:
        draw_markdown_lines(draw, pilmoji, lines_tokens, text_start_x, text_y, line_spacing, text_color, {
            "normal": font,
            "bold": bold_font,
            "italic": font,
            "bold_italic": bold_font
        })

    os.makedirs("video", exist_ok=True)
    filename = os.path.join("video", f"message_{message_index}_{role}.png")
    try:
        img.save(filename)
        logging.info(f"Saved Discord-style message: {filename}")
    except Exception as e:
        logging.error(f"Error saving image: {e}")

    return img

def merge_config(role, config):
    default_cfg = config.get("default", {})
    role_cfg = config.get(role, {})
    merged = default_cfg.copy()
    merged.update(role_cfg)
    return merged

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
        speaker_config = merge_config(role, config)
        if not speaker_config:
            logging.error(f"Missing configuration for role: {role}")
            continue
        for msg_obj in entry.get("messages", []):
            text = msg_obj.get("text", "")
            if previous_role is None or role == previous_role:
                accumulated_messages.append(text)
            else:
                accumulated_messages = [text]
            previous_role = role

            generate_message_block(accumulated_messages, role, message_index, speaker_config)
            message_index += 1

if __name__ == "__main__":
    main()
