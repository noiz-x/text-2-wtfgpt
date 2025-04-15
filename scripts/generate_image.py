# scripts/generate_image.py

import json
import os
import re
import logging
import textwrap
from PIL import Image, ImageDraw, ImageFont
from pilmoji import Pilmoji
from pilmoji.source import GoogleEmojiSource
import argparse

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# === Utility Functions for Markdown Parsing ===

def parse_markdown(text):
    """
    Parses a string containing Markdown-style formatting markers into tokens.
    Supported markers (non-nested):
      - Bold & Italic: ***text***
      - Bold: **text**
      - Italic: *text*
      - Strikethrough: ~~text~~
    Returns a list of tokens. Each token is a dict:
       { "text": <str>, "bold": <bool>, "italic": <bool>, "strikethrough": <bool> }
    """
    # Triple-asterisk tokens are handled first
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
    """
    Choose the appropriate font for a token based on its style flags.
    The fonts dictionary is expected to have keys:
      - normal (required)
      - bold (optional)
      - italic (optional)
      - bold_italic (optional)
    """
    if token["bold"] and token["italic"]:
        return fonts.get("bold_italic", fonts["normal"])
    elif token["bold"]:
        return fonts.get("bold", fonts["normal"])
    elif token["italic"]:
        return fonts.get("italic", fonts["normal"])
    else:
        return fonts["normal"]

def wrap_tokens(tokens, draw, fonts, max_width):
    """
    Wrap the list of tokens into multiple lines so that each line's total width does not exceed max_width.
    This is a simple word-wrapping routine.
    Returns a list of lines; each line is a list of tokens.
    
    Modified to replace any newline characters in token text with spaces
    so that textlength measurements don't error out.
    """
    lines = []
    current_line = []
    current_width = 0

    for token in tokens:
        # Split the token text by spaces.
        words = token["text"].split(" ")
        for i, word in enumerate(words):
            # Append a space if not the last word.
            word_text = word + (" " if i < len(words) - 1 else "")
            # Replace any newline characters.
            word_text = word_text.replace("\n", " ")
            ttoken = {
                "text": word_text,
                "bold": token["bold"],
                "italic": token["italic"],
                "strikethrough": token["strikethrough"]
            }
            font_used = select_font(ttoken, fonts)
            word_width = draw.textlength(ttoken["text"], font=font_used)
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
    """
    Draws the wrapped token lines onto the image.
    For each token, uses the appropriate font.
    If a token has strikethrough enabled, draws a line over it.
    Returns the total height occupied.
    """
    y = start_y
    line_height = 0
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
        line_height = max_line_height
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

def generate_text_profile(name, bg_color, text_color, size, font_path):
    if not name:
        return None
    profile_img = Image.new("RGBA", (size, size))
    draw = ImageDraw.Draw(profile_img)
    draw.ellipse((0, 0, size, size), fill=bg_color)
    initials = name[:2].upper()
    try:
        font = ImageFont.truetype(font_path, size // 2)
    except IOError:
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), initials, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    x = (size - text_width) // 2
    y = (size - text_height) // 2
    draw.text((x, y), initials, fill=text_color, font=font)
    return profile_img

def generate_chatgpt_message_block(accumulated_messages, role, message_index, config):
    message_text = "\n".join(accumulated_messages)
    cleaned_message_text = re.sub(r'\[SFX:[^\]]+\]', '', message_text)
    
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
    profile_name = config.get("profile_name", "").strip()
    profile_size = config.get("profile_size", 50)
    profile_gap = config.get("profile_gap", 10)
    profile_bg = config.get("profile_bg", "#555555")
    profile_text_color = config.get("profile_text_color", "#FFFFFF")
    feedback_padding_top = config.get("feedback_padding_top", 5)
    feedback_padding_bottom = config.get("feedback_padding_bottom", 5)

    fonts = {}
    try:
        fonts["normal"] = ImageFont.truetype(font_path, font_size)
    except IOError:
        fonts["normal"] = ImageFont.load_default()
    fonts["bold"] = ImageFont.truetype(config.get("bold_font_path", font_path), font_size) if config.get("bold_font_path") else fonts["normal"]
    fonts["italic"] = ImageFont.truetype(config.get("italic_font_path", font_path), font_size) if config.get("italic_font_path") else fonts["normal"]
    fonts["bold_italic"] = ImageFont.truetype(config.get("bold_italic_font_path", font_path), font_size) if config.get("bold_italic_font_path") else fonts["normal"]

    has_profile = bool(profile_image_path) or bool(profile_name)
    profile_x = horizontal_padding if has_profile else 0
    text_start_x = profile_x + (profile_size + profile_gap if has_profile else horizontal_padding)

    tokens = parse_markdown(cleaned_message_text)
    dummy_img = Image.new("RGB", (block_width, 100), background_color)
    dummy_draw = ImageDraw.Draw(dummy_img)
    max_text_width = block_width - text_start_x - horizontal_padding
    lines_tokens = wrap_tokens(tokens, dummy_draw, fonts, max_text_width)
    
    total_text_height = 0
    for line in lines_tokens:
        bbox = dummy_draw.textbbox((0,0), "Ag", font=fonts["normal"])
        line_height = bbox[3] - bbox[1]
        total_text_height += line_height + line_spacing
    total_text_height -= line_spacing

    try:
        name_font = ImageFont.truetype(font_path, max(font_size - 4, 12))
    except IOError:
        name_font = ImageFont.load_default()
    name_height = name_font.getbbox("Ag")[3] + 4 if (has_profile and profile_name) else 0
    bubble_height = total_text_height + 2 * vertical_padding
    feedback_height = fonts["normal"].getbbox("Ag")[3]

    content_height = name_height + bubble_height + feedback_padding_top + feedback_height + feedback_padding_bottom
    total_height = max((profile_size + 2 * vertical_padding) if has_profile else 0, content_height + vertical_padding)

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
        if profile_img:
            profile_img = profile_img.resize((profile_size, profile_size))
            mask = Image.new("L", (profile_size, profile_size), 0)
            ImageDraw.Draw(mask).ellipse((0, 0, profile_size, profile_size), fill=255)
            profile_img.putalpha(mask)
            profile_y = (total_height - profile_size) // 2
            img.paste(profile_img, (profile_x, profile_y), profile_img)

    if has_profile and profile_name:
        name_x = text_start_x
        name_y = vertical_padding
        draw.text((name_x, name_y), profile_name, font=name_font, fill="#ffffff")
    else:
        name_y = vertical_padding

    bubble_y0 = name_y + (name_height + 6 if (has_profile and profile_name) else 0)
    max_line_width = 0
    for line in lines_tokens:
        line_width = 0
        for token in line:
            token_font = select_font(token, fonts)
            line_width += dummy_draw.textlength(token["text"], font=token_font)
        max_line_width = max(max_line_width, line_width)
    bubble_x0 = text_start_x
    bubble_x1 = bubble_x0 + max_line_width + 2 * horizontal_padding
    bubble_y1 = bubble_y0 + bubble_height
    draw.rounded_rectangle([bubble_x0, bubble_y0, bubble_x1, bubble_y1], radius=20, fill=bubble_color)

    with Pilmoji(img, source=GoogleEmojiSource) as pilmoji:
        text_draw_x = bubble_x0 + horizontal_padding
        text_draw_y = bubble_y0 + vertical_padding
        draw_markdown_lines(draw, pilmoji, lines_tokens, text_draw_x, text_draw_y, line_spacing, text_color, fonts)

    feedback_text = "👍   👎"
    feedback_width = draw.textlength(feedback_text, font=fonts["normal"])
    feedback_x = bubble_x1 - feedback_width - horizontal_padding
    feedback_y = bubble_y1 + feedback_padding_top
    draw.text((feedback_x, feedback_y), feedback_text, font=fonts["normal"], fill="#aaaaaa")
    
    os.makedirs("video", exist_ok=True)
    image_filename = os.path.join("video", f"message_{message_index}_{role}.png")
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
        speaker_config = config.get(role) or config.get("default")
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
