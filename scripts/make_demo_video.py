#!/usr/bin/env python3
"""Cinematic BountyPilot AI demo renderer (PIL + ffmpeg)."""
import subprocess, os, sys, math, random, time
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops, ImageEnhance

DEMO_FILE = '/tmp/demo_output.txt'
OUT_VIDEO = '/data/data/com.termux/files/home/bountypilot-ai/bountypilot-demo.mp4'
FRAME_DIR = '/tmp/cinematic_frames'
os.makedirs(FRAME_DIR, exist_ok=True)
for f in os.listdir(FRAME_DIR):
    os.remove(os.path.join(FRAME_DIR, f))

W, H = 1920, 1080
FPS = 30
random.seed(7)

with open(DEMO_FILE) as f:
    content = f.read()
lines = content.split('\n')
print(f"{len(lines)} lines")

FONT_DIR = '/usr/share/fonts/truetype/dejavu'
def load(name, size):
    p = os.path.join(FONT_DIR, name)
    return ImageFont.truetype(p, size) if os.path.exists(p) else ImageFont.load_default()

FONT_SIZE = 20
LINE_H = 24
TITLE_SIZE = 104
SUB_SIZE = 40
TAG_SIZE = 28
BODY_SIZE = 34
OUTRO_SIZE = 46

font      = load('DejaVuSansMono.ttf', FONT_SIZE)
font_bold = load('DejaVuSansMono-Bold.ttf', FONT_SIZE)
font_sans = load('DejaVuSans.ttf', SUB_SIZE)
font_sans_bold = load('DejaVuSans-Bold.ttf', SUB_SIZE)
font_sans_tag = load('DejaVuSans.ttf', TAG_SIZE)
font_sans_body = load('DejaVuSans.ttf', BODY_SIZE)
font_sans_outro = load('DejaVuSans-Bold.ttf', OUTRO_SIZE)

# --- cinematic color grade ---
BG        = (24, 22, 28)
PANEL     = (44, 43, 52)
PANEL_ALT = (36, 35, 44)
BORDER    = (72, 240, 150)
BORDER_DIM= (45, 150, 95)
TEXT      = (240, 236, 226)
DIM       = (150, 154, 148)
GREEN     = (90, 250, 170)
YELLOW    = (255, 210, 90)
RED       = (255, 110, 80)
BLUE      = (140, 190, 255)
PURPLE    = (200, 160, 255)
TITLE_FG  = (255, 255, 255)
ACCENT    = (90, 250, 170)
GLOW      = (48, 200, 100)

# --- word-wrap a line to fit within max_px ---
def wrap_line(line, fnt, max_px):
    if not line:
        return ['']
    if fnt.getlength(line) <= max_px:
        return [line]
    out = []
    cur = ''
    for w in line.split(' '):
        trial = (cur + ' ' + w).strip()
        if fnt.getlength(trial) <= max_px:
            cur = trial
        else:
            if cur:
                out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    return out or [line]

# --- classify a source line into (color, font) for rendering ---
def classify(line):
    s = line.strip()
    if s.startswith('# '):
        return GREEN, font_bold
    if s.startswith('$ '):
        return GREEN, font_bold
    if s.startswith('✔') or s.startswith('PASS') or s.startswith('All checks'):
        return GREEN, font
    if s.startswith('MISS'):
        return DIM, font
    if s.startswith('Readiness') or s.startswith('Owner-only') or s.startswith('Note:'):
        return YELLOW, font
    if s.startswith('  - ') or s.startswith('│') or s.startswith('╭') or s.startswith('├') or s.startswith('╰'):
        return DIM, font
    if s.startswith('Source:'):
        return DIM, font
    if s.startswith('State:'):
        return YELLOW, font
    return TEXT, font

# --- layout constants for the terminal panel ---
PANEL_X, PANEL_Y = 90, 120
PANEL_W, PANEL_H = 1740, 840
PANEL_R = 18
PANEL_PAD = 34
TEXT_MAX_W = PANEL_W - 2 * PANEL_PAD
TITLE_BAR_H = 52
TITLE_BAR_Y = PANEL_Y + 18
CONTENT_TOP = TITLE_BAR_Y + TITLE_BAR_H
CONTENT_H = PANEL_Y + PANEL_H - 26
MAX_LINES = (CONTENT_H - CONTENT_TOP) // LINE_H

# --- build the flat list of (text, color, font) display rows ---
def build_rows():
    rows = []
    for line in lines:
        color, fnt = classify(line)
        for w in wrap_line(line, fnt, TEXT_MAX_W):
            rows.append((w, color, fnt))
    return rows

ROWS = build_rows()
print(f"{len(ROWS)} display rows (max {MAX_LINES} visible)")

# --- draw a soft radial vignette over the image ---
def vignette(img, strength=0.18):
    """Radial gradient: bright (keep image) at center, dark (blend to BG) at edges."""
    w, h = img.size
    step = 24
    sw, sh = max(1, w // step), max(1, h // step)
    mask = Image.new('L', (sw, sh), 0)
    px = mask.load()
    cx, cy = sw / 2.0, sh / 2.0
    r = max(sw, sh) * 0.82
    for yy in range(sh):
        for xx in range(sw):
            dist = math.hypot(xx - cx, yy - cy)
            v = max(0.0, 1.0 - dist / r)
            px[xx, yy] = int(255 * (v ** 1.4) * strength)
    mask = mask.resize((w, h), Image.BILINEAR).filter(ImageFilter.GaussianBlur(120))
    return Image.composite(img, Image.new('RGB', (w, h), BG), mask)

# --- draw subtle moving film grain ---
_noise_cache = {}
def grain(img):
    w, h = img.size
    key = (w, h)
    if key not in _noise_cache:
        n_rgb = Image.effect_noise((w, h), 10).convert('RGB')
        n_rgb = n_rgb.filter(ImageFilter.GaussianBlur(0.5))
        n_l = n_rgb.convert('L')
        _noise_cache[key] = (n_rgb, n_l)
    n_rgb, n_l = _noise_cache[key]
    return Image.composite(img, Image.blend(img, n_rgb, 0.055), n_l)

# --- scene: TITLE CARD ---
def draw_title(t):
    img = Image.new('RGB', (W, H), BG)
    # soft green glow blob (RGBA so the outside stays transparent)
    glow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    pulse = 0.5 + 0.5 * math.sin(t * 1.6)
    gx, gy = W // 2, int(H * 0.42)
    rr = int(560 + 80 * pulse)
    gd.ellipse([gx - rr, gy - rr, gx + rr, gy + rr], fill=GLOW + (150,))
    glow = glow.filter(ImageFilter.GaussianBlur(220))
    img = Image.alpha_composite(img.convert('RGBA'), glow).convert('RGB')
    # second, wider halo
    glow2 = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    gd2 = ImageDraw.Draw(glow2)
    gd2.ellipse([gx - 900, gy - 700, gx + 900, gy + 700], fill=(14, 70, 34, 80))
    glow2 = glow2.filter(ImageFilter.GaussianBlur(320))
    img = Image.alpha_composite(img.convert('RGBA'), glow2).convert('RGB')
    d = ImageDraw.Draw(img)
    # title
    tw = font_sans_outro.getlength("BountyPilot AI")
    d.text(((W - tw) / 2, int(H * 0.30) - 50), "BountyPilot AI", fill=(255, 255, 255), font=font_sans_outro)
    # subtitle
    sub = "Discover opportunities. Evaluate bounties. Execute with confidence."
    sw = font_sans_body.getlength(sub)
    d.text(((W - sw) / 2, int(H * 0.30) + 60), sub, fill=ACCENT, font=font_sans_body)
    # tags
    tags = ["CLI", "Solana", "Gibwork", "Hackathon Ready"]
    tx = W // 2 - 420
    ty = int(H * 0.30) + 130
    for tag in tags:
        tw2 = font_sans_tag.getlength(tag) + 46
        d.rounded_rectangle([tx, ty, tx + tw2, ty + 46], radius=23, outline=ACCENT, width=2)
        d.text((tx + 23, ty + 9), tag, fill=ACCENT, font=font_sans_tag)
        tx += tw2 + 18
    return vignette(img, 0.9)

# --- scene: TERMINAL ---
def draw_terminal(visible_rows, t):
    img = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(img)
    # panel
    pulse = 0.5 + 0.5 * math.sin(t * 1.2)
    border_col = tuple(int(BORDER_DIM[i] + (BORDER[i] - BORDER_DIM[i]) * pulse) for i in range(3))
    d.rounded_rectangle([PANEL_X, PANEL_Y, PANEL_X + PANEL_W, PANEL_Y + PANEL_H],
                        radius=PANEL_R, fill=PANEL, outline=border_col, width=3)
    # title bar
    d.rounded_rectangle([PANEL_X, TITLE_BAR_Y, PANEL_X + PANEL_W, TITLE_BAR_Y + TITLE_BAR_H],
                        radius=PANEL_R, fill=(16, 16, 20))
    for i, col in enumerate([(255, 95, 64), (255, 198, 52), (56, 204, 140)]):
        cx = PANEL_X + 34 + i * 40
        d.ellipse([cx, TITLE_BAR_Y + 16, cx + 22, TITLE_BAR_Y + 38], fill=col)
    host = "festac@bountypilot-ai"
    d.text((PANEL_X + 118, TITLE_BAR_Y + 13), host, fill=(170, 170, 178), font=font)
    # rows
    y = CONTENT_TOP
    for row_text, row_color, row_font in visible_rows:
        d.text((PANEL_X + PANEL_PAD, y), row_text, fill=row_color, font=row_font)
        y += LINE_H
    # blinking cursor
    if math.sin(t * 3.0) > 0:
        cy = CONTENT_TOP + (len(visible_rows)) * LINE_H - LINE_H + 4
        d.rectangle([PANEL_X + PANEL_PAD + font_bold.getlength(visible_rows[-1][0]) + 6, cy - 2,
                     PANEL_X + PANEL_PAD + font_bold.getlength(visible_rows[-1][0]) + 16, cy + 16],
                    fill=GREEN)
    return vignette(img, 0.9)

# --- scene: OUTRO ---
def draw_outro(t):
    img = Image.new('RGB', (W, H), BG)
    glow = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gx, gy = W // 2, int(H * 0.5)
    gd.ellipse([gx - 520, gy - 520, gx + 520, gy + 520], fill=GLOW + (150,))
    glow = glow.filter(ImageFilter.GaussianBlur(280))
    img = Image.alpha_composite(img.convert('RGBA'), glow).convert('RGB')
    glow2 = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    gd2 = ImageDraw.Draw(glow2)
    gd2.ellipse([gx - 900, gy - 700, gx + 900, gy + 700], fill=(14, 70, 34, 90))
    glow2 = glow2.filter(ImageFilter.GaussianBlur(320))
    img = Image.alpha_composite(img.convert('RGBA'), glow2).convert('RGB')
    d = ImageDraw.Draw(img)
    tw = font_sans_outro.getlength("BountyPilot AI")
    d.text(((W - tw) / 2, int(H * 0.36)), "BountyPilot AI", fill=TITLE_FG, font=font_sans_outro)
    sub = "Evaluation-to-submission pipeline for Gibwork bounties."
    sw = font_sans_body.getlength(sub)
    d.text(((W - sw) / 2, int(H * 0.36) + 70), sub, fill=ACCENT, font=font_sans_body)
    cmd = "git clone https://github.com/festac-dev/bountypilot-ai && pip install -e ."
    cw = font.getlength(cmd)
    d.text(((W - cw) / 2, int(H * 0.36) + 150), cmd, fill=(190, 194, 188), font=font)
    d.text((W // 2 - font_bold.getlength("bountypilot") - 14, int(H * 0.36) + 196), "bountypilot",
           fill=GREEN, font=font_bold)
    return vignette(img, 0.9)

# --- MAIN ANIMATION ---
# Pacing: reveal rows progressively, hold after commands/headers.
# Each row takes 2 frames to appear; $ commands hold 60 frames; # headers hold 90 frames.
FPS = 30
frame_idx = 0

def emit(fn, count):
    global frame_idx
    for _ in range(count):
        fn(frame_idx)
        frame_idx += 1

def save_frame(img, idx):
    img = ImageEnhance.Brightness(img).enhance(2.3)   # cinematic lift
    img = grain(img)
    path = os.path.join(FRAME_DIR, f'frame_{idx:06d}.png')
    for attempt in range(6):
        try:
            img.save(path)
            return
        except OSError:
            time.sleep(0.2)
    raise OSError(f'giving up on {path}')

# Title card: 4s
for i in range(int(4.0 * FPS)):
    save_frame(draw_title(i / FPS), frame_idx); frame_idx += 1

# Terminal: progressive reveal
row_idx = 0
N = len(ROWS)
while row_idx < N:
    # reveal next row over 2 frames
    visible = ROWS[:row_idx + 1]
    if len(visible) > MAX_LINES:
        visible = visible[-MAX_LINES:]
    save_frame(draw_terminal(visible, frame_idx / FPS), frame_idx); frame_idx += 1
    save_frame(draw_terminal(visible, frame_idx / FPS), frame_idx); frame_idx += 1
    row_idx += 1
    # pacing hold based on the SOURCE line this row came from
    src = lines[row_idx - 1] if row_idx - 1 < len(lines) else ''
    if src.startswith('$ '):
        hold = 60   # 2s after a command
    elif src.startswith('# '):
        hold = 90   # 3s after a section header
    else:
        hold = 0
    for _ in range(hold):
        save_frame(draw_terminal(visible, frame_idx / FPS), frame_idx); frame_idx += 1

# Terminal end hold: 3s
for _ in range(int(3.0 * FPS)):
    save_frame(draw_terminal(ROWS[-MAX_LINES:], frame_idx / FPS), frame_idx); frame_idx += 1

# Outro: 5s
for i in range(int(5.0 * FPS)):
    save_frame(draw_outro(i / FPS), frame_idx); frame_idx += 1

dur = frame_idx / FPS
print(f"Generated {frame_idx} frames = {dur:.1f}s")

# --- FFMPEG ASSEMBLY (video + soundtrack) ---
# Build a mixed soundtrack: pad + ticking + thock on keystrokes + pulse + riser + final chord.
SS = '/tmp/soundtrack'
def mix_audio():
    # inputs: 0=video(no audio), 1=pad, 2=tick, 3=riser, 4=chord
    pad = "[1:a]volume=0.22,aloop=loop=-1:size=44100[a0]"
    tick = "[2:a]volume=0.16,aloop=loop=-1:size=44100[a1]"
    riser_start = max(0, int(dur) - 3)
    riser = f"[3:a]volume=0.20,fade=t=in:0:3,fade=t=out:{riser_start}:3,adelay={riser_start*1000}[a2]"
    chord_start = max(0, int(dur) - 2)
    chord = f"[4:a]volume=0.32,fade=t=in:0:1,fade=t=out:{chord_start}:2,adelay={chord_start*1000}[a3]"
    filt = f"{pad};{tick};{riser};{chord};[a0][a1][a2][a3]amix=inputs=4:duration=longest:dropout_transition=0,volume=1.2[aout]"
    return filt

af = mix_audio()
cmd = [
    'ffmpeg', '-y',
    '-framerate', str(FPS),
    '-i', os.path.join(FRAME_DIR, 'frame_%06d.png'),
    '-i', f'{SS}/pad.wav',
    '-i', f'{SS}/tick.wav',
    '-i', f'{SS}/riser.wav',
    '-i', f'{SS}/chord.wav',
    '-filter_complex', af,
    '-map', '0:v', '-map', '[aout]',
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '18',
    '-pix_fmt', 'yuv420p',
    '-c:a', 'aac', '-b:a', '192k',
    '-shortest',
    OUT_VIDEO
]
print("Running ffmpeg...")
subprocess.run(cmd, check=True)
print(f"Video created: {OUT_VIDEO}")
print(f"Size: {os.path.getsize(OUT_VIDEO)} bytes")
print(f"Duration: {dur:.1f}s")
