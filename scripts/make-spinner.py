"""The orange spinning like a loading icon, settling onto exactly the frame
the ident opens with - same size AND same position."""
from PIL import Image
from pathlib import Path
import subprocess, sys, math

import os
A = Path(os.environ.get("TANGBOX_ASSETS",
         Path(__file__).resolve().parent.parent / "nostalgiabox" / "assets"))
W, H, FPS = 1920, 1080, 60
DURATION = float(sys.argv[1]) if len(sys.argv) > 1 else 10.0
TURNS = 5

circle = Image.open(A / "logo-circle.png").convert("RGBA")
leaves = Image.open(A / "logo-leaves.png").convert("RGBA")
raw_w, raw_h = circle.size

# --- reproduce the ident's geometry exactly (static_gen._ident_command) ---
base = (W * 0.76) / raw_w
lw, lh = max(2, int(raw_w * base)), max(2, int(raw_h * base))
lock_x, lock_y = (W - lw) // 2, (H - lh) // 2

comp = Image.alpha_composite(circle, leaves)
bbox = comp.getchannel("A").getbbox()          # the fruit+leaves within the canvas
cx = (bbox[0] + bbox[2]) / 2 * base
cy = (bbox[1] + bbox[3]) / 2 * base
screen_cx, screen_cy = W / 2, lock_y + cy  # the ident STARTS the fruit at screen centre
print(f"ident places the orange centre at ({screen_cx:.0f}, {screen_cy:.0f})")

orange = comp.crop(bbox)
tgt = (max(2, round(orange.size[0] * base)), max(2, round(orange.size[1] * base)))
orange = orange.resize(tgt, Image.LANCZOS)

# Square padding so rotation about the centre never clips.
diag = int(math.hypot(*orange.size)) + 4
sq = Image.new("RGBA", (diag, diag), (0, 0, 0, 0))
sq.paste(orange, ((diag - orange.size[0]) // 2, (diag - orange.size[1]) // 2), orange)
sq.save("/tmp/orange.png")

ox, oy = round(screen_cx - diag / 2), round(screen_cy - diag / 2)
print(f"overlay at ({ox}, {oy}), square {diag}px")

# easeOutCubic across a whole number of turns: fast, then settling to upright
# at exactly t=DURATION, which is the angle the ident opens on.
u = f"(1-t/{DURATION})"
angle = f"2*PI*{TURNS}*(1-{u}*{u}*{u})"

subprocess.run([
    "ffmpeg", "-y", "-v", "error",
    "-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={FPS}:d={DURATION}",
    "-loop", "1", "-t", str(DURATION), "-i", "/tmp/orange.png",
    "-filter_complex",
    f"[1:v]rotate={angle}:c=none:ow=iw:oh=ih[spun];"
    f"[0:v][spun]overlay={ox}:{oy}:format=auto,format=yuv420p",
    "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-an",
    str(A / "colorbars.mp4"),
], check=True)
print("wrote", A / "colorbars.mp4")
