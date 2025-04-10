# generate_image.py

import json
import os
import textwrap
from PIL import Image, ImageDraw, ImageFont, ImageOps
from pilmoji import Pilmoji
from pilmoji.source import GoogleEmojiSource

def load_conversation(conversation_file="conversation.json"):
    """Load conversation data from the JSON file."""
    with open(conversation_file, "r") as f:
        return json.load(f)

def load_config(config_file="config.json"):
    """Load configuration data from the JSON file."""
    with open(config_file, "r") as f:
        return json.load(f)

def generate_text_profile(name, bg_color, text_color, size, font_path):
    """Generate a circular profile image with the speaker's initials."""
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
    """Generate an image for the accumulated messages from a specific speaker."""
    message_text = "\n".join(accumulated_messages)
    background_color = config["background_color"]
    bubble_color = config["bubble_color"]
    text_color = config["text_color"]
    font_path = config["font_path"]
    font_size = config["font_size"]
    block_width = config["block_width"]
    vertical_padding = config["vertical_padding"]
    horizontal_padding = config["horizontal_padding"]
    line_spacing = config["line_spacing"]
    profile_image_path = config.get("profile_image_path", None)
    profile_name = config["profile_name"]
    profile_size = config["profile_size"]
    profile_gap = config["profile_gap"]
    profile_bg = config["profile_bg"]
    profile_text_color = config["profile_text_color"]
    feedback_padding_top = config["feedback_padding_top"]
    feedback_padding_bottom = config["feedback_padding_bottom"]

    # Load fonts
    try:
        font = ImageFont.truetype(font_path, font_size)
        name_font = ImageFont.truetype(font_path, font_size - 4)
    except IOError:
        font = ImageFont.load_default()
        name_font = ImageFont.load_default()

    # Layout calculations
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

    # Draw profile image
    if has_profile:
        if profile_image_path:
            try:
                profile_img = Image.open(profile_image_path).convert("RGBA")
            except Exception:
                profile_img = generate_text_profile(profile_name, profile_bg, profile_text_color, profile_size, font_path)
        else:
            profile_img = generate_text_profile(profile_name, profile_bg, profile_text_color, profile_size, font_path)
        profile_img = profile_img.resize((profile_size, profile_size))
        mask = Image.new("L", (profile_size, profile_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, profile_size, profile_size), fill=255)
        profile_img.putalpha(mask)
        profile_y = (total_height - profile_size) // 2
        img.paste(profile_img, (profile_x, profile_y), profile_img)

    # Draw speaker name
    name_x = text_start_x
    name_y = vertical_padding
    draw.text((name_x, name_y), profile_name, font=name_font, fill="#ffffff")

    # Draw chat bubble
    bubble_x0 = text_start_x
    bubble_y0 = name_y + name_height + 6
    bubble_x1 = bubble_x0 + text_width + 2 * horizontal_padding
    bubble_y1 = bubble_y0 + bubble_height
    draw.rounded_rectangle([bubble_x0, bubble_y0, bubble_x1, bubble_y1], radius=20, fill=bubble_color)

    # Draw message text
    text_draw_x = bubble_x0 + horizontal_padding
    text_draw_y = bubble_y0 + vertical_padding
    with Pilmoji(img, source=GoogleEmojiSource) as pilmoji:
        pilmoji.text((text_draw_x, text_draw_y), wrapped_text, font=font, fill=text_color, spacing=line_spacing)

    # Draw feedback line
    feedback_text = "👍   👎"
    feedback_font = font
    feedback_width = draw.textlength(feedback_text, font=feedback_font)
    feedback_x = bubble_x1 - feedback_width - horizontal_padding
    feedback_y = bubble_y1 + feedback_padding_top
    draw.text((feedback_x, feedback_y), feedback_text, font=feedback_font, fill="#aaaaaa")

    os.makedirs("output", exist_ok=True)
    image_filename = f"output/message_{message_index}_{role}.png"
    img.save(image_filename)
    print(f"Saved image for {role} message block {message_index}: {image_filename}")
    return img

def main():
    conversation = load_conversation()
    config = load_config()

    message_index = 1
    previous_role = None
    accumulated_messages = []
    
    # Process each entry in the conversation
    for entry in conversation["conversation"]:
        role = entry["role"]
        speaker_config = config["user"] if role == "user" else config["assistant"]
        for msg_obj in entry["messages"]:
            text = msg_obj["text"]
            # If the same speaker continues, accumulate; otherwise, reset accumulation.
            if previous_role is None or role == previous_role:
                accumulated_messages.append(text)
            else:
                accumulated_messages = [text]
            previous_role = role

            generate_chatgpt_message_block(accumulated_messages, role, message_index, speaker_config)
            message_index += 1

if __name__ == "__main__":
    main()
