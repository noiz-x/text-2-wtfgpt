import json
import os
import re
import logging
import sys
import argparse
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from pilmoji import Pilmoji
from pilmoji.source import GoogleEmojiSource

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# === Markdown Parsing Utilities ===

def parse_markdown(text):
    pattern = re.compile(r'(\*\*\*.*?\*\*\*|\*\*.*?\*\*|\*.*?\*|~~.*?~~)')
    tokens, last_idx = [], 0
    for match in pattern.finditer(text):
        if match.start() > last_idx:
            tokens.append({"text": text[last_idx:match.start()], "bold": False, "italic": False, "strikethrough": False})
        token = match.group(0)
        if token.startswith("***"):
            tokens.append({"text": token[3:-3], "bold": True, "italic": True, "strikethrough": False})
        elif token.startswith("**"):
            tokens.append({"text": token[2:-2], "bold": True, "italic": False, "strikethrough": False})
        elif token.startswith("*"):
            tokens.append({"text": token[1:-1], "bold": False, "italic": True, "strikethrough": False})
        elif token.startswith("~~"):
            tokens.append({"text": token[2:-2], "bold": False, "italic": False, "strikethrough": True})
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
    emoji_re = re.compile(
        "[" 
        "\U0001F300-\U0001F5FF"
        "\U0001F600-\U0001F64F"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "]+", 
        flags=re.UNICODE
    )
    for ch in text:
        if emoji_re.match(ch):
            total += font.getmask(ch).size[0] * emoji_adjustment_factor
        else:
            bb = draw.textbbox((0,0), ch, font=font)
            total += (bb[2] - bb[0]) if bb else 0
    return total

def wrap_tokens(tokens, draw, fonts, max_width):
    lines, line, width = [], [], 0
    for token in tokens:
        for i, word in enumerate(token["text"].split(" ")):
            wtext = word + (" " if i < len(token["text"].split(" ")) - 1 else "")
            tkn = {**token, "text": wtext}
            fnt = select_font(tkn, fonts)
            w = custom_textlength(draw, wtext, fnt)
            if line and width + w > max_width:
                lines.append(line)
                line, width = [], 0
            line.append(tkn)
            width += w
    if line:
        lines.append(line)
    return lines

def draw_markdown_lines(draw, pilmoji, lines, x0, y0, spacing, fill, fonts):
    y = y0
    for line in lines:
        x, max_h = x0, 0
        for token in line:
            fnt = select_font(token, fonts)
            pilmoji.text((x, y), token["text"], font=fnt, fill=fill)
            bb = draw.textbbox((0,0), token["text"], font=fnt)
            w, h = bb[2]-bb[0], bb[3]-bb[1]
            if token.get("strikethrough"):
                draw.line((x, y + h/2, x + w, y + h/2), fill=fill, width=1)
            x += w
            max_h = max(max_h, h)
        y += max_h + spacing
    return y - y0

def extract_first_url(text):
    match = re.search(r'https?://\S+', text)
    return match.group(0) if match else None

# === Fix here: cast to int to avoid float offsets ===
def draw_reactions(
    draw,
    pilmoji,
    reactions,
    x,
    y,
    emoji_font,
    count_font=None,
    *,
    # Discord‑style defaults:
    bg_color="#282d51",          # pill background
    outline_color="#393f88",     # pill border
    text_color="#DCDFE4",        # emoji & count
    radius=12,                   # pill corner radius
    inner_pad_x=12,               # horizontal padding inside pill
    inner_pad_y=8,               # vertical padding inside pill
    item_spacing=6,              # spacing between pills
    icon_spacing=15              # spacing between emoji & count
):
    """
    Draws Discord‑style reaction pills with better padding & colors.
    Returns the baseline y + height of tallest pill.
    """
    if count_font is None:
        count_font = emoji_font

    max_h = 0
    for reaction in reactions:
        emoji = reaction["emoji"]
        count_text = str(reaction["count"])

        # Measure emoji & count
        eb = draw.textbbox((0,0), emoji, font=emoji_font)
        cb = draw.textbbox((0,0), count_text, font=count_font)
        ew, eh = eb[2]-eb[0], eb[3]-eb[1]
        cw, ch = cb[2]-cb[0], cb[3]-cb[1]

        # Pill dimensions
        pill_w = inner_pad_x*2 + ew + icon_spacing + cw
        pill_h = inner_pad_y*2 + max(eh, ch)

        # Draw background pill
        rect = [x, y, x + pill_w, y + pill_h]
        draw.rounded_rectangle(rect, radius=radius, fill=bg_color, outline=outline_color)

        # Center emoji vertically
        ey = y + (pill_h - eh) // 3.5
        px = x + inner_pad_x
        pilmoji.text((px, int(ey)), emoji, font=emoji_font, fill=text_color)

        # Draw count next, centered
        px += ew + icon_spacing
        cy = y + (pill_h - ch) // 3
        draw.text((px, cy), count_text, font=count_font, fill=text_color)

        # Advance
        x += pill_w + item_spacing
        max_h = max(max_h, pill_h)

    return y + max_h

def draw_link_preview(draw, x, y, width, url, font):
    padding = 10
    height = 40
    box_color = "#f2f3f5"
    text_color = "#0066cc"
    draw.rounded_rectangle((x, y, x + width, y + height), radius=6, fill=box_color)
    draw.text((x + padding, y + 10), url, font=font, fill=text_color)
    return height + 6

def load_json(path):
    try:
        with open(path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed loading {path}: {e}")
    return {}

def generate_text_profile(name, bg, fg, size, font_path, r=0.2):
    H = size * 4
    img = Image.new('RGBA', (H, H), bg)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0,0,H,H), int(H*r), fill=bg)
    initials = name[:2].upper()
    try:
        fnt = ImageFont.truetype(font_path, H//2)
    except IOError:
        fnt = ImageFont.load_default()
    bb = draw.textbbox((0,0), initials, font=fnt)
    w, h = bb[2]-bb[0], bb[3]-bb[1]
    draw.text(((H-w)/2,(H-h)/2), initials, font=fnt, fill=fg)
    return img.resize((size,size), Image.LANCZOS)

def generate_avatar(path, size):
    T = size * 4
    im = Image.open(path).convert('RGBA')
    im.thumbnail((sys.maxsize, T), Image.LANCZOS)
    w, h = im.size
    d = min(w,h)
    im = im.crop(((w-d)//2,(h-d)//2,(w-d)//2+d,(h-d)//2+d))
    mask = Image.new('L', (d,d), 0)
    ImageDraw.Draw(mask).ellipse((0,0,d,d), fill=255)
    im.putalpha(mask)
    return im.resize((size,size), Image.LANCZOS)

def merge_config(role, cfg):
    default = cfg.get('default', {})
    role_cfg = cfg.get(role, {})
    merged = {**default, **role_cfg}
    for r, col in default.get('role_colors', {}).items():
        if r == role:
            merged['username_color'] = col
            break
    return merged

def generate_message_block(messages, role, idx, cfg):
    full_text = "\n".join(m['text'] for m in messages)
    full_text = re.sub(r'\[SFX:[^\]]+\]', '', full_text)

    c = merge_config(role, cfg)
    bg, fg = c['background_color'], c['text_color']
    uname_col = c['username_color']

    now = datetime.now()
    first = messages[0]
    ts_str = now.strftime("Today at %-I:%M %p")
    if 'timestamp' in first:
        try:
            dt = datetime.fromisoformat(first['timestamp'])
            if dt.date() == now.date():
                ts_str = dt.strftime("Today at %-I:%M %p")
            else:
                ts_str = dt.strftime("%b %d, %Y at %-I:%M %p")
        except ValueError:
            pass
    if first.get('edited', False):
        ts_str += " (edited)"

    fp, bfp = c['font_path'], c.get('bold_font_path', c['font_path'])
    sz = c.get('font_size', 24)
    try:
        font = ImageFont.truetype(fp, sz)
        bold = ImageFont.truetype(bfp, sz)
        ts_font = ImageFont.truetype(fp, sz-6)
        emoji_font = ImageFont.truetype(fp, sz-6)
    except IOError:
        font = bold = ts_font = emoji_font = ImageFont.load_default()

    W = c['block_width']
    av = c['profile_size']
    px, py = c['horizontal_padding'], c['vertical_padding']
    gap, ls = c['profile_gap'], c['line_spacing']

    dummy = Image.new('RGB', (W,100), bg)
    dd = ImageDraw.Draw(dummy)
    tokens = parse_markdown(full_text)
    max_w = W - (px*2 + av + gap)
    lines = wrap_tokens(tokens, dd, {
        'normal': font, 'bold': bold,
        'italic': font, 'bold_italic': bold
    }, max_w)

    name_h = bold.getbbox("Ag")[3]
    text_height = len(lines) * (name_h + ls)
    link = extract_first_url(full_text)
    link_preview_h = 50 if link else 0
    reactions = first.get("reactions", [])
    reaction_h = 30 if reactions else 0
    total_extra = link_preview_h + reaction_h
    H = max(av + 2*py, name_h + text_height + total_extra + 2*py)

    img = Image.new('RGBA', (W, int(H)), (0,0,0,0))
    dr = ImageDraw.Draw(img)
    dr.rounded_rectangle((0,0,W,H), radius=8, fill=bg)

    if c.get('profile_image_path') and os.path.exists(c['profile_image_path']):
        try:
            av_img = generate_avatar(c['profile_image_path'], av)
        except Exception:
            av_img = generate_text_profile(c.get('profile_name','?'), "#7289da", "#ffffff", av, fp)
    else:
        av_img = generate_text_profile(c.get('profile_name','?'), "#7289da", "#ffffff", av, fp)

    HR = av * 4
    border = Image.new('RGBA', (HR,HR), (0,0,0,0))
    bdr = ImageDraw.Draw(border)
    bw = max(2, HR//40)
    bdr.ellipse((0,0,HR,HR), fill='#ffffff')
    mask = Image.new('L', (HR,HR), 0)
    ImageDraw.Draw(mask).ellipse((bw,bw,HR-bw,HR-bw), fill=255)
    border.paste(av_img.resize((HR,HR), Image.LANCZOS), (0,0), mask)
    avatar = border.resize((av,av), Image.LANCZOS)
    img.paste(avatar, (px, py), avatar)

    x0, y0 = px + av + gap, py
    dr.text((x0, y0), c.get('profile_name','?'), font=bold, fill=uname_col)
    name_w = dr.textlength(c.get('profile_name','?'), font=bold)
    dr.text((x0 + name_w + 8, y0 + 2), ts_str, font=ts_font, fill="gray")

    with Pilmoji(img, source=GoogleEmojiSource) as p:
        y_msg = y0 + name_h + 4
        draw_markdown_lines(dr, p, lines, x0, y_msg, ls, fg, {
            'normal': font, 'bold': bold,
            'italic': font, 'bold_italic': bold
        })

        y_offset = y_msg + text_height

        if link:
            y_offset += draw_link_preview(dr, x0, y_offset, max_w, link, font)

        if reactions:
            y_offset += draw_reactions(dr, p, reactions, x0, y_offset, emoji_font)

    os.makedirs('video', exist_ok=True)
    out = os.path.join('video', f'message_{idx}_{role}.png')
    try:
        img.save(out)
        logging.info(f"Saved: {out}")
    except Exception as e:
        logging.error(f"Error saving image: {e}")

    return img

def main():
    parser = argparse.ArgumentParser(description="Generate Discord‑style chat images.")
    parser.add_argument('--conversation', default='utils/conversation.json')
    parser.add_argument('--config',       default='utils/config.json')
    args = parser.parse_args()

    conv = load_json(args.conversation)
    cfg  = load_json(args.config)
    if not conv or not cfg:
        return

    idx, prev = 1, None
    acc = []

    for entry in conv.get('conversation', []):
        role = entry.get('role')
        for msg in entry.get('messages', []):
            if prev and role != prev:
                acc = []
            acc.append(msg)
            prev = role
            generate_message_block(acc, role, idx, cfg)
            idx += 1

if __name__ == '__main__':
    main()
