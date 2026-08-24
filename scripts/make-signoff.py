"""The sign-off: the ident run backwards, then the orange collapsing like a CRT.

The box opened with a five-second animated ident and closed with a
three-quarter-second white circle. This makes the ending its own mirror:
the letters slide back in behind the fruit, and then the fruit itself does
the collapse rather than an unrelated white blob.
"""
from PIL import Image, ImageDraw
from pathlib import Path
import subprocess, math, shutil, tempfile

import os
A = Path(os.environ.get("TANGBOX_ASSETS",
         Path(__file__).resolve().parent.parent / "nostalgiabox" / "assets"))
W, H, FPS = 1920, 1080, 60
RETRACT_SPEED = 1.6            # play the reversed ident this much faster
SQUASH, PINCH, WINK = 0.30, 0.22, 0.18     # seconds per collapse phase

# --- the orange, exactly as the ident draws it at rest -------------------
circle = Image.open(A / "logo-circle.png").convert("RGBA")
leaves = Image.open(A / "logo-leaves.png").convert("RGBA")
raw_w, raw_h = circle.size
base = (W * 0.76) / raw_w
lh = max(2, int(raw_h * base))
lock_y = (H - lh) // 2
comp = Image.alpha_composite(circle, leaves)
bbox = comp.getchannel("A").getbbox()
cx, cy = W / 2, lock_y + (bbox[1] + bbox[3]) / 2 * base
orange = comp.crop(bbox)
orange = orange.resize(
    (max(2, round(orange.size[0] * base)), max(2, round(orange.size[1] * base))),
    Image.LANCZOS,
)
ow, oh = orange.size

tmp = Path(tempfile.mkdtemp())
n = 0

def frame():
    return Image.new("RGB", (W, H), (0, 0, 0))

def save(im):
    global n
    im.save(tmp / f"f{n:05d}.png"); n += 1

# Phase 1 - squash vertically to a bright line.
for i in range(int(SQUASH * FPS)):
    t = i / (SQUASH * FPS)
    im = frame()
    h = max(2, int(oh * (1 - t) + 3 * t))
    sq = orange.resize((ow, h), Image.LANCZOS)
    # bleach toward white as it flattens, the way a CRT line blooms
    if t > 0.4:
        white = Image.new("RGBA", sq.size, (255, 255, 255, 255))
        sq = Image.blend(sq, Image.composite(white, sq, sq.getchannel("A")), (t - 0.4) / 0.6)
    im.paste(sq, (int(cx - ow / 2), int(cy - h / 2)), sq)
    save(im)

# Phase 2 - the line pinches in to a dot.
for i in range(int(PINCH * FPS)):
    t = i / (PINCH * FPS)
    im = frame()
    w = max(2, int(ow * (1 - t) + 4 * t))
    d = ImageDraw.Draw(im)
    d.rectangle([cx - w / 2, cy - 2, cx + w / 2, cy + 2], fill=(255, 255, 255))
    save(im)

# Phase 3 - the dot fades.
for i in range(int(WINK * FPS)):
    t = i / (WINK * FPS)
    im = frame()
    v = int(255 * (1 - t))
    r = max(1, 4 * (1 - t) + 1)
    ImageDraw.Draw(im).ellipse([cx - r, cy - r, cx + r, cy + r], fill=(v, v, v))
    save(im)

print(f"{n} collapse frames")
subprocess.run([
    "ffmpeg", "-y", "-v", "error", "-framerate", str(FPS),
    "-i", str(tmp / "f%05d.png"),
    "-c:v", "libx264", "-preset", "medium", "-crf", "18",
    "-pix_fmt", "yuv420p", str(tmp / "collapse.mp4"),
], check=True)

# --- the ident, backwards --------------------------------------------------
subprocess.run([
    "ffmpeg", "-y", "-v", "error", "-i", str(A / "logo.mp4"),
    "-vf", f"reverse,setpts=PTS/{RETRACT_SPEED}", "-an",
    "-c:v", "libx264", "-preset", "medium", "-crf", "18",
    "-pix_fmt", "yuv420p", str(tmp / "retract.mp4"),
], check=True)

# --- join them -------------------------------------------------------------
(tmp / "list.txt").write_text(
    f"file '{tmp}/retract.mp4'\nfile '{tmp}/collapse.mp4'\n", encoding="utf-8"
)
if (A / "power_off.mp4").exists() and not (A / "power_off-crt.mp4").exists():
    shutil.copy(A / "power_off.mp4", A / "power_off-crt.mp4")
subprocess.run([
    "ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
    "-i", str(tmp / "list.txt"), "-c", "copy", str(A / "power_off.mp4"),
], check=True)
print("wrote", A / "power_off.mp4")
