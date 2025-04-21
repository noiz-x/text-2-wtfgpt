import json
import os
import re
import logging
import sys
import argparse
import copy
from datetime import datetime
from PIL import Image, ImageDraw, ImageFont
from pilmoji import Pilmoji
from pilmoji.source import GoogleEmojiSource

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# -----------------------------------------------------------------------------
# JSON Loader
# -----------------------------------------------------------------------------
def load_json(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed loading {path}: {e}")
        return None

# -----------------------------------------------------------------------------
# Markdown + Emoji Drawing Helpers
# -----------------------------------------------------------------------------
def parse_markdown(text):
    pattern = re.compile(r'(\*\*\*.*?\*\*\*|\*\*.*?\*\*|\*.*?\*|~~.*?~~)')
    tokens, last = [], 0
    for m in pattern.finditer(text):
        if m.start() > last:
            tokens.append({"text": text[last:m.start()], "bold": False, "italic": False, "strikethrough": False})
        t = m.group(0)
        if t.startswith("***"):
            tokens.append({"text": t[3:-3], "bold": True, "italic": True, "strikethrough": False})
        elif t.startswith("**"):
            tokens.append({"text": t[2:-2], "bold": True, "italic": False, "strikethrough": False})
        elif t.startswith("*"):
            tokens.append({"text": t[1:-1], "bold": False, "italic": True, "strikethrough": False})
        elif t.startswith("~~"):
            tokens.append({"text": t[2:-2], "bold": False, "italic": False, "strikethrough": True})
        last = m.end()
    if last < len(text):
        tokens.append({"text": text[last:], "bold": False, "italic": False, "strikethrough": False})
    return tokens

def select_font(token, fonts):
    if token["bold"] and token["italic"]:
        return fonts.get("bold_italic", fonts["normal"])
    if token["bold"]:
        return fonts.get("bold", fonts["normal"])
    if token["italic"]:
        return fonts.get("italic", fonts["normal"])
    return fonts["normal"]

def custom_textlength(draw, text, font, emoji_factor=1.5):
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
            total += font.getmask(ch).size[0] * emoji_factor
        else:
            bb = draw.textbbox((0,0), ch, font=font)
            total += (bb[2] - bb[0]) if bb else 0
    return total

def wrap_tokens(tokens, draw, fonts, max_width):
    lines, line, w_acc = [], [], 0
    for token in tokens:
        words = token["text"].split(" ")
        for i, w in enumerate(words):
            txt = w + (" " if i < len(words)-1 else "")
            tk = {**token, "text": txt}
            f = select_font(tk, fonts)
            w_len = custom_textlength(draw, txt, f)
            if line and w_acc + w_len > max_width:
                lines.append(line)
                line, w_acc = [], 0
            line.append(tk)
            w_acc += w_len
    if line:
        lines.append(line)
    return lines

def draw_markdown_lines(draw, pilmoji, lines, x0, y0, spacing, fill, fonts):
    y = y0
    for line in lines:
        x, max_h = x0, 0
        for tk in line:
            f = select_font(tk, fonts)
            pilmoji.text((x, y), tk["text"], font=f, fill=fill)
            bb = draw.textbbox((0,0), tk["text"], font=f)
            w, h = bb[2]-bb[0], bb[3]-bb[1]
            if tk.get("strikethrough"):
                draw.line((x, y + h/2, x + w, y + h/2), fill=fill, width=1)
            x += w
            max_h = max(max_h, h)
        y += max_h + spacing
    return y - y0

def extract_first_url(text):
    m = re.search(r'https?://\S+', text)
    return m.group(0) if m else None

def draw_reactions(draw, pilmoji, reactions, x, y, emoji_font, count_font=None,
                   bg="#282d51", outline="#393f88", txtcol="#DCDFE4",
                   rad=12, pad_x=12, pad_y=8, spacing=6, icon_sp=15):
    cf = count_font or emoji_font
    max_h = 0
    for r in reactions:
        e, cnt = r["emoji"], str(r["count"])
        eb = draw.textbbox((0,0), e, font=emoji_font)
        cb = draw.textbbox((0,0), cnt, font=cf)
        ew, eh = eb[2]-eb[0], eb[3]-eb[1]
        cw, ch = cb[2]-cb[0], cb[3]-cb[1]
        w_pill = pad_x*2 + ew + icon_sp + cw
        h_pill = pad_y*2 + max(eh, ch)
        rect = [x, y, x+w_pill, y+h_pill]
        draw.rounded_rectangle(rect, radius=rad, fill=bg, outline=outline)
        ey = y + (h_pill - eh)//3.5
        pilmoji.text((x+pad_x, int(ey)), e, font=emoji_font, fill=txtcol)
        nx = x+pad_x+ew+icon_sp
        cy = y + (h_pill - ch)//3
        draw.text((nx, cy), cnt, font=cf, fill=txtcol)
        x += w_pill + spacing
        max_h = max(max_h, h_pill)
    return y + max_h

def draw_link_preview(draw, x, y, width, url, font):
    pad, h = 10, 40
    draw.rounded_rectangle((x, y, x+width, y+h), radius=6, fill="#f2f3f5")
    draw.text((x+pad, y+10), url, font=font, fill="#0066cc")
    return h + 6

# -----------------------------------------------------------------------------
# Profile / Avatar
# -----------------------------------------------------------------------------
def generate_text_profile(name, bg, fg, size, font_path, r=0.2):
    H = size * 4
    img = Image.new('RGBA', (H, H), bg)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0,0,H,H), int(H*r), fill=bg)
    initials = name[:2].upper()
    try:
        fnt = ImageFont.truetype(font_path, H//2)
    except IOError:
        fnt = ImageFont.load_default()
    bb = d.textbbox((0,0), initials, font=fnt)
    w, h = bb[2]-bb[0], bb[3]-bb[1]
    d.text(((H-w)//2, (H-h)//2), initials, font=fnt, fill=fg)
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

# -----------------------------------------------------------------------------
# Config Merge
# -----------------------------------------------------------------------------
def merge_config(role, cfg):
    default = cfg.get('default', {})
    role_cfg = cfg.get(role, {})
    merged = {**default, **role_cfg}
    for r, col in default.get('role_colors', {}).items():
        if r == role:
            merged['username_color'] = col
            break
    return merged

# -----------------------------------------------------------------------------
# Message Block (no saving!)
# -----------------------------------------------------------------------------
def generate_message_block(messages, role, cfg):
    c     = merge_config(role, cfg)
    bg    = c['background_color']
    fg    = c['text_color']
    uname_col = c['username_color']
    W     = c['block_width']
    av    = c['profile_size']
    px, py = c['horizontal_padding'], c['vertical_padding']
    gap, ls = c['profile_gap'], c['line_spacing']

    now = datetime.now()
    first = messages[0]
    ts = now.strftime("Today at %-I:%M %p")
    if 'timestamp' in first:
        try:
            dt = datetime.fromisoformat(first['timestamp'])
            ts = dt.strftime("Today at %-I:%M %p") if dt.date()==now.date() else dt.strftime("%b %d, %Y at %-I:%M %p")
        except:
            pass
    if first.get('edited', False):
        ts += " (edited)"

    fp, bfp = c['font_path'], c.get('bold_font_path', c['font_path'])
    sz = c.get('font_size', 24)
    try:
        font    = ImageFont.truetype(fp, sz)
        bold    = ImageFont.truetype(bfp, sz)
        ts_font = ImageFont.truetype(fp, sz-6)
        emoji_font = ImageFont.truetype(fp, sz-6)
    except IOError:
        font = bold = ts_font = emoji_font = ImageFont.load_default()

    dummy = Image.new('RGB', (W,1000), bg)
    dd = ImageDraw.Draw(dummy)
    max_w = W - (px*2 + av + gap)
    all_lines = []
    for seg in messages:
        text = re.sub(r'\[SFX:[^\]]+\]', '', seg['text'])
        tokens = parse_markdown(text)
        lines = wrap_tokens(tokens, dd, {'normal': font, 'bold': bold, 'italic': font, 'bold_italic': bold}, max_w)
        all_lines.extend(lines)

    name_h = bold.getbbox("Ag")[3]
    text_h = len(all_lines) * (name_h + ls)
    link = extract_first_url("\n".join(m['text'] for m in messages))
    link_h = 50 if link else 0
    reactions = first.get('reactions', [])
    react_h = 30 if reactions else 0
    H = max(av + 2*py, name_h + text_h + link_h + react_h + 2*py)

    img = Image.new('RGBA', (W, int(H)), (0,0,0,0))
    dr  = ImageDraw.Draw(img)
    dr.rounded_rectangle((0,0,W,H), radius=8, fill=bg)

    if c.get('profile_image_path') and os.path.exists(c['profile_image_path']):
        try:
            av_img = generate_avatar(c['profile_image_path'], av)
        except:
            av_img = generate_text_profile(c.get('profile_name','?'), "#7289da", "#fff", av, fp)
    else:
        av_img = generate_text_profile(c.get('profile_name','?'), "#7289da", "#fff", av, fp)

    HR = av*4
    border = Image.new('RGBA', (HR,HR), (0,0,0,0))
    bdr = ImageDraw.Draw(border)
    bw = max(2, HR//40)
    bdr.ellipse((0,0,HR,HR), fill='#fff')
    mask = Image.new('L', (HR,HR), 0)
    ImageDraw.Draw(mask).ellipse((bw,bw,HR-bw,HR-bw), fill=255)
    border.paste(av_img.resize((HR,HR), Image.LANCZOS), (0,0), mask)
    avatar = border.resize((av,av), Image.LANCZOS)
    img.paste(avatar, (px, py), avatar)

    x0, y0 = px + av + gap, py
    dr.text((x0, y0), c.get('profile_name','?'), font=bold, fill=uname_col)
    n_w = dr.textlength(c.get('profile_name','?'), font=bold)
    dr.text((x0 + n_w + 8, y0 + 2), ts, font=ts_font, fill="gray")

    with Pilmoji(img, source=GoogleEmojiSource) as pilmoji:
        y_text = y0 + name_h + 4
        draw_markdown_lines(dr, pilmoji, all_lines, x0, y_text, ls, fg, 
                            {'normal': font, 'bold': bold, 'italic': font, 'bold_italic': bold})
        y_off = y_text + text_h
        if link:
            y_off += draw_link_preview(dr, x0, y_off, max_w, link, font)
        if reactions:
            y_off += draw_reactions(dr, pilmoji, reactions, x0, y_off, emoji_font)

    return img

# -----------------------------------------------------------------------------
# Join/Leave Block
# -----------------------------------------------------------------------------
def generate_join_or_leave_message(name, time, template, arrow_x, arrow_img, color, cfg):
    jc = cfg.get("join_leave", {})
    W  = jc.get("world_width", 900)
    H  = jc.get("world_height", 100)
    bg = cfg["default"].get("background_color", "#36393F")
    fnt_size = cfg["default"].get("font_size", 24)
    msg_f  = ImageFont.truetype(cfg["default"]["font_path"], fnt_size)
    name_f = ImageFont.truetype(cfg["default"].get("bold_font_path", cfg["default"]["font_path"]), fnt_size)
    time_f = ImageFont.truetype(cfg["default"]["font_path"], fnt_size-6)
    before, after = template.split("CHARACTER")
    time_str = f"Today at {time} PM"
    img = Image.new('RGBA', (W, H), bg)
    dr  = ImageDraw.Draw(img)
    arr = Image.open(arrow_img).convert('RGBA')
    arr.thumbnail((40,40), Image.LANCZOS)
    ascent,_ = msg_f.getmetrics()
    txt_h = msg_f.getbbox("Ag")[3] - msg_f.getbbox("Ag")[1]
    y0 = (H - txt_h)//2
    ay = y0 + (ascent - arr.height)//2
    img.paste(arr, (arrow_x, ay), arr)
    x0 = arrow_x + arr.width + 60
    with Pilmoji(img, source=GoogleEmojiSource) as pilmoji:
        pilmoji.text((x0, y0), before, cfg["default"].get("joined_font_color", "#e0e0e0"), font=msg_f)
        nx = x0 + msg_f.getbbox(before)[2]
        pilmoji.text((nx, y0), name, color, font=name_f)
        pilmoji.text((nx + name_f.getbbox(name)[2], y0), after, cfg["default"].get("joined_font_color", "#e0e0e0"), font=msg_f)
        dr.text((nx + msg_f.getbbox(before+name+after)[2] + 30, y0), time_str, font=time_f, fill=cfg["default"].get("time_font_color", "#888"))
    return img

# -----------------------------------------------------------------------------
# Sequencing Generators
# -----------------------------------------------------------------------------
def iter_system_images(entry, cfg):
    jc      = cfg.get("join_leave", {})
    arrow_x = jc.get("arrow_x", 40)
    g_arr   = os.path.join("assets", "arrow_join.png")
    l_arr   = os.path.join("assets", "arrow_leave.png")
    for msg in entry.get('messages', []):
        txt = msg.get('text', '')
        ts  = msg.get('timestamp')
        try:
            tstr = datetime.fromisoformat(ts).strftime("%-I:%M")
        except:
            tstr = "00:00"
        lower = txt.lower()
        if 'joined' in lower:
            name = txt.split(' joined')[0]
            yield generate_join_or_leave_message(
                name, tstr,
                "CHARACTER joined the server", arrow_x, g_arr,
                cfg['default']['role_colors'].get('user','#fff'),
                cfg
            )
        elif 'left' in lower:
            name = txt.split(' left')[0]
            yield generate_join_or_leave_message(
                name, tstr,
                "CHARACTER left the server", arrow_x, l_arr,
                cfg['default']['role_colors'].get('user','#fff'),
                cfg
            )

def iter_message_blocks(entry, cfg):
    role     = entry.get('role')
    messages = entry.get('messages', [])

    # typing build-up
    for count in range(1, len(messages)):
        subset = copy.deepcopy(messages[:count])
        for flag in ('timestamp','edited'):
            if flag in entry:
                subset[0][flag] = entry[flag]
        subset[0].pop('reactions', None)
        yield generate_message_block(subset, role, cfg)

    # full + reactions
    full = copy.deepcopy(messages)
    for flag in ('timestamp','edited'):
        if flag in entry:
            full[0][flag] = entry[flag]

    state = {}
    for ev in entry.get('reactions', []):
        state[ev['emoji']] = ev['count']
        full[0]['reactions'] = [{"emoji": e, "count": state[e]} for e in state]
        yield generate_message_block(full, role, cfg)

    if not entry.get('reactions'):
        full[0].pop('reactions', None)
        yield generate_message_block(full, role, cfg)

def iter_all_images(conv, cfg):
    for entry in conv.get('conversation', []):
        if entry.get('role') == 'system':
            yield from iter_system_images(entry, cfg)
        else:
            yield from iter_message_blocks(entry, cfg)

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Generate Discord‑style chat images.")
    parser.add_argument('--conversation', default='utils/conversation.json')
    parser.add_argument('--config',       default='utils/config.json')
    args = parser.parse_args()

    conv = load_json(args.conversation)
    cfg  = load_json(args.config)
    if not conv or not cfg:
        sys.exit(1)

    os.makedirs('video', exist_ok=True)
    for idx, img in enumerate(iter_all_images(conv, cfg), start=1):
        filename = f"{idx:04d}.png"
        path     = os.path.join('video', filename)
        img.save(path)
        logging.info(f"Saved: {path}")

if __name__ == '__main__':
    main()
