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

# === Markdown Parsing Utilities ===

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
            tokens.append({"text": token_text[3:-3], "bold": True, "italic": True, "strikethrough": False})
        elif token_text.startswith("**") and token_text.endswith("**"):
            tokens.append({"text": token_text[2:-2], "bold": True, "italic": False, "strikethrough": False})
        elif token_text.startswith("*") and token_text.endswith("*"):
            tokens.append({"text": token_text[1:-1], "bold": False, "italic": True, "strikethrough": False})
        elif token_text.startswith("~~") and token_text.endswith("~~"):
            tokens.append({"text": token_text[2:-2], "bold": False, "italic": False, "strikethrough": True})
        last_idx = match.end()
    if last_idx < len(text):
        tokens.append({"text": text[last_idx:], "bold": False, "italic": False, "strikethrough": False})
    return tokens

def select_font(token, fonts):
    if token["bold"] and token["italic"]:
        return fonts.get("bold_italic", fonts["normal"])
    if token["bold"]:
        return fonts.get("bold", fonts["normal"])
    if token["italic"]:
        return fonts.get("italic", fonts["normal"])
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
            total += font.getmask(char).size[0] * emoji_adjustment_factor
        else:
            bbox = draw.textbbox((0, 0), char, font=font)
            total += (bbox[2] - bbox[0]) if bbox else 0
    return total

def wrap_tokens(tokens, draw, fonts, max_width):
    lines, current_line, current_width = [], [], 0
    for token in tokens:
        parts = token["text"].split(" ")
        for i, part in enumerate(parts):
            word = part + (" " if i < len(parts)-1 else "")
            t = {**token, "text": word}
            font_used = select_font(t, fonts)
            w = custom_textlength(draw, word, font_used)
            if current_line and current_width + w > max_width:
                lines.append(current_line)
                current_line, current_width = [], 0
            current_line.append(t)
            current_width += w
    if current_line:
        lines.append(current_line)
    return lines

def draw_markdown_lines(draw, pilmoji, lines, x0, y0, spacing, fill, fonts):
    y = y0
    for line in lines:
        x, max_h = x0, 0
        for token in line:
            font = select_font(token, fonts)
            pilmoji.text((x, y), token["text"], font=font, fill=fill)
            bbox = draw.textbbox((0, 0), token["text"], font=font)
            w, h = bbox[2]-bbox[0], bbox[3]-bbox[1]
            if token.get("strikethrough"):
                draw.line((x, y + h/2, x + w, y + h/2), fill=fill, width=1)
            x += w
            max_h = max(max_h, h)
        y += max_h + spacing
    return y - y0

# === JSON Load Helper ===

def load_json(path):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed loading {path}: {e}")
    return {}

# === Profile & Avatar Generation ===

def generate_text_profile(name, bg, fg, size, font_path, r=0.2):
    scale, H = 4, size * 4
    img = Image.new('RGBA', (H, H), bg)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0,0,H,H), radius=int(H*r), fill=bg)
    initials = name[:2].upper()
    try:
        font = ImageFont.truetype(font_path, H//2)
    except IOError:
        font = ImageFont.load_default()
    bb = draw.textbbox((0,0), initials, font=font)
    w, h = bb[2]-bb[0], bb[3]-bb[1]
    draw.text(((H-w)/2, (H-h)/2), initials, font=font, fill=fg)
    return img.resize((size, size), Image.LANCZOS)

def generate_avatar(image_path, size):
    scale, T = 4, size * 4
    im = Image.open(image_path).convert('RGBA')
    im.thumbnail((sys.maxsize, T), Image.LANCZOS)
    w, h = im.size
    d = min(w, h)
    im = im.crop(((w-d)//2, (h-d)//2, (w-d)//2 + d, (h-d)//2 + d))
    mask = Image.new('L', (d, d), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, d, d), fill=255)
    im.putalpha(mask)
    return im.resize((size, size), Image.LANCZOS)

# === Config Merge with Role Colors ===

def merge_config(role, cfg):
    default = cfg.get('default', {})
    role_cfg = cfg.get(role, {})
    merged = {**default, **role_cfg}
    colors = default.get('role_colors', {})
    if role in colors:
        merged['username_color'] = colors[role]
    return merged

# === Message Block Generation ===

def generate_message_block(acc_msgs, role, idx, cfg):
    # Clean and combine text
    text = "\n".join(m.strip() for m in acc_msgs)
    text = re.sub(r'\[SFX:[^\]]+\]', '', text)

    c = merge_config(role, cfg)
    bg, fg = c['background_color'], c['text_color']
    uname_col = c['username_color']

    ts = datetime.now().strftime("%-I:%M %p")
    timestamp = f"Today at {ts}"

    # Fonts
    fp, bfp = c['font_path'], c.get('bold_font_path', c['font_path'])
    sz = c.get('font_size', 24)
    try:
        font = ImageFont.truetype(fp, sz)
        bold = ImageFont.truetype(bfp, sz)
        ts_font = ImageFont.truetype(fp, sz - 6)
    except IOError:
        font = bold = ts_font = ImageFont.load_default()

    # Layout metrics
    W = c['block_width']; av = c['profile_size']
    px, py = c['horizontal_padding'], c['vertical_padding']
    gap, ls = c['profile_gap'], c['line_spacing']

    # Prepare text lines
    dummy = Image.new('RGB', (W, 100), bg)
    dd = ImageDraw.Draw(dummy)
    tokens = parse_markdown(text)
    max_w = W - (px*2 + av + gap)
    lines = wrap_tokens(tokens, dd, {
        "normal": font, "bold": bold,
        "italic": font, "bold_italic": bold
    }, max_w)
    line_h = dd.textbbox((0,0),"Ag",font=font)[3]
    txt_h = len(lines)*(line_h + ls)
    name_h = bold.getbbox("Ag")[3]
    H = max(av + 2*py, name_h + txt_h + 2*py)

    # Base image
    img = Image.new('RGBA', (W, int(H)), (0,0,0,0))
    dr = ImageDraw.Draw(img)
    dr.rounded_rectangle((0,0,W,H), radius=8, fill=bg)

    # Avatar with border
    if c.get('profile_image_path') and os.path.exists(c['profile_image_path']):
        try:
            av_img = generate_avatar(c['profile_image_path'], av)
        except Exception:
            av_img = generate_text_profile(c.get('profile_name','?'),
                                           "#7289da","#ffffff", av, fp)
    else:
        av_img = generate_text_profile(c.get('profile_name','?'),
                                       "#7289da","#ffffff", av, fp)

    HR = av * 4
    border = Image.new('RGBA', (HR, HR), (0,0,0,0))
    bdr = ImageDraw.Draw(border)
    bw = max(2, HR//40)
    bdr.ellipse((0,0,HR,HR), fill='#ffffff')
    mask = Image.new('L', (HR, HR), 0)
    ImageDraw.Draw(mask).ellipse((bw,bw,HR-bw,HR-bw), fill=255)
    avatar_hr = av_img.resize((HR, HR), Image.LANCZOS)
    border.paste(avatar_hr, (0,0), mask)
    avatar = border.resize((av, av), Image.LANCZOS)
    img.paste(avatar, (px, py), avatar)

    # Username & timestamp
    x0, y0 = px + av + gap, py
    dr.text((x0, y0), c.get('profile_name','?'), font=bold, fill=uname_col)
    nw = dr.textlength(c.get('profile_name','?'), font=bold)
    dr.text((x0 + nw + 8, y0 + 2), timestamp, font=ts_font, fill="gray")

    # Message text
    with Pilmoji(img, source=GoogleEmojiSource) as p:
        draw_markdown_lines(dr, p, lines, x0, y0 + name_h + 4, ls, fg, {
            "normal": font, "bold": bold,
            "italic": font, "bold_italic": bold
        })

    # Save
    os.makedirs('video', exist_ok=True)
    out = os.path.join('video', f'message_{idx}_{role}.png')
    try:
        img.save(out)
        logging.info(f"Saved Discord-style message: {out}")
    except Exception as e:
        logging.error(f"Error saving image: {e}")

    return img

def main():
    parser = argparse.ArgumentParser(description="Generate Discord-style chat images.")
    parser.add_argument('--conversation', default='utils/conversation.json')
    parser.add_argument('--config', default='utils/config.json')
    args = parser.parse_args()

    conv = load_json(args.conversation)
    cfg = load_json(args.config)
    if not conv or not cfg:
        return

    idx, prev, acc = 1, None, []
    for entry in conv.get('conversation', []):
        role = entry.get('role')
        for m in entry.get('messages', []):
            txt = m.get('text','')
            if prev and role != prev:
                acc = [txt]
            else:
                acc.append(txt)
            prev = role
            generate_message_block(acc, role, idx, cfg)
            idx += 1

if __name__ == '__main__':
    main()
