"""A 3x3 inch sticker sheet: the logo on black, on white, and on the test card.

Three equal one-inch bands, wordmark pinned to 2.50in in each so the type is
identical down the sheet. 1800x1800 at 600 DPI, which prints at exactly 3x3.

    python3 scripts/make-stickers.py

Needs Pillow and ffmpeg. Writes to ~/Downloads, or TANGBOX_STICKER_OUT.
"""
from PIL import Image, ImageEnhance, ImageFilter
from pathlib import Path

import os, subprocess, tempfile

ROOT = Path(__file__).resolve().parent.parent
ASSETS = Path(os.environ.get("TANGBOX_ASSETS", ROOT / "nostalgiabox" / "assets"))
OUT_DIR = Path(os.environ.get("TANGBOX_STICKER_OUT", Path.home() / "Downloads"))

SRC = ASSETS / "logo.png"
# One frame of the box's own test card, rather than bars invented for the job.
BARS = Path(tempfile.gettempdir()) / "tangbox-bars.png"
if not BARS.exists():
    subprocess.run(["ffmpeg", "-v", "error", "-i", str(ASSETS / "colorbars-smpte.mp4"),
                    "-frames:v", "1", "-y", str(BARS)], check=True)
DPI = 600
SIZE = 3 * DPI                  # 1800px = 3in
BAND = SIZE // 3                # 600px = 1in each
WORDMARK_W = int(2.50 * DPI)    # 2.50in, matching the standalone split sticker
GLOW_BLUR = 22                  # px of soft dark halo on the test-card band
GLOW_PASSES = 3                 # composited repeatedly to deepen it

src = Image.open(SRC).convert("RGBA")

def is_lettering(r, g, b, a):
    return a > 0 and r > 200 and g > 200 and b > 200

def recolour_text(im, to):
    out = im.copy(); px = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = px[x, y]
            if is_lettering(r, g, b, a):
                px[x, y] = (*to, a)
    return out

def fit(art, max_w, max_h):
    s = min(max_w / art.width, max_h / art.height)
    return art.resize((round(art.width * s), round(art.height * s)), Image.LANCZOS)

def glowed(art, blur, passes):
    """A soft dark halo behind everything, so it survives the bars.

    White lettering disappears over the white bar and black lettering
    disappears over blue - neither colour works alone on a test card. A hard
    outline fixes that but reads as a sticker-cut edge; a blurred shadow does
    the same job and leaves the letterforms clean.

    Composited several times rather than once: a single blurred pass is far
    too faint to darken a white bar, and simply raising the blur only spreads
    the same little ink thinner.
    """
    pad = blur * 3
    big = Image.new("RGBA", (art.width + pad * 2, art.height + pad * 2), (0, 0, 0, 0))
    big.paste(art, (pad, pad), art)

    halo_a = big.getchannel("A").filter(ImageFilter.GaussianBlur(blur))
    halo = Image.new("RGBA", big.size, (0, 0, 0, 0))
    halo.paste((0, 0, 0, 255), (0, 0), halo_a)

    out = Image.new("RGBA", big.size, (0, 0, 0, 0))
    for _ in range(passes):
        out.alpha_composite(halo)
    out.alpha_composite(big)
    return out

canvas = Image.new("RGB", (SIZE, SIZE), (255, 255, 255))

# 1 - black
canvas.paste((0, 0, 0), (0, 0, SIZE, BAND))
# 3 - the test card, cropped to the band's shape then filled
bars = Image.open(BARS).convert("RGB")

# Crop to the COLOUR region only. A full SMPTE frame is mostly not colourful:
# the outer bars are grey, and the bottom third is PLUGE and a greyscale ramp.
# Taking the whole frame put all of that in the band and it read as murky.
w, h = bars.size
bars = bars.crop((int(w * 0.125), 0, int(w * 0.875), int(h * 0.583)))

# And lift them. Broadcast bars are 75% amplitude on purpose - correct for
# calibrating a monitor, dull on a sticker.
bars = ImageEnhance.Color(bars).enhance(1.45)
bars = ImageEnhance.Brightness(bars).enhance(1.08)

scale = max(SIZE / bars.width, BAND / bars.height)
bars = bars.resize((round(bars.width * scale), round(bars.height * scale)), Image.LANCZOS)
left = (bars.width - SIZE) // 2
top_ = (bars.height - BAND) // 2
canvas.paste(bars.crop((left, top_, left + SIZE, top_ + BAND)), (0, BAND * 2))

pieces = [
    (src.copy(),                     0,        False),   # white on black
    (recolour_text(src, (0, 0, 0)),  BAND,     False),   # black on white
    (src.copy(),                     BAND * 2, True),    # white + dark glow, on bars
]
for art, top, outline in pieces:
    art = fit(art, WORDMARK_W, BAND - 2 * int(0.10 * DPI))
    if outline:
        art = glowed(art, GLOW_BLUR, GLOW_PASSES)
    canvas.paste(art, ((SIZE - art.width) // 2, top + (BAND - art.height) // 2), art)
    print(f"  band y={top:<5} {art.width}x{art.height}px "
          f"({art.width/DPI:.2f}x{art.height/DPI:.2f}in){'  glowed' if outline else ''}")

OUT_DIR.mkdir(parents=True, exist_ok=True)
out = OUT_DIR / "tangbox-sticker-3in-three.jpg"
canvas.save(out, "JPEG", quality=95, dpi=(DPI, DPI), subsampling=0)
print(f"{out.name}: {canvas.size}px @ {DPI}dpi = 3x3in, bands {BAND}px = 1in each")
