"""Generate the nostalgic filler clips (analog static, SMPTE colour bars).

These short clips are what make channel changes feel like a real 2000s TV:

* ``static.mp4`` - a second of silent grey "snow", shown briefly whenever the
  channel changes.
* ``colorbars.mp4`` - SMPTE colour bars with a 1 kHz tone, shown at start-up and
  as a friendly "no signal" / empty-channel screen.

They are produced once (by ``scripts/install.sh`` or ``python -m
nostalgiabox.static_gen``) with ffmpeg and cached in the assets directory, so
the Pi never has to synthesise them at runtime.
"""

from __future__ import annotations

import argparse
import logging
import shutil
from functools import lru_cache
import subprocess
from pathlib import Path
from typing import List, Optional

log = logging.getLogger(__name__)

# Package-bundled assets live next to this file.
DEFAULT_ASSETS_DIR = Path(__file__).resolve().parent / "assets"

STATIC_FILENAME = "static.mp4"
COLORBARS_FILENAME = "colorbars.mp4"
LOGO_FILENAME = "logo.mp4"
# Brian's wordmark, white on transparent, rasterised from brand/. When this
# is present the ident is built from it; otherwise a placeholder is drawn.
LOGO_IMAGE_FILENAME = "logo.png"
# The wordmark split into pieces, so the ident can ANIMATE them separately:
# one layer per letter (logo-g0..g5) plus the fruit. The letters slide OUT FROM
# BEHIND the fruit at constant size - they never scale and never fade.
LOGO_GLYPH_PREFIX = "logo-g"
LOGO_LAYER_CIRCLE = "logo-circle.png"
# The leaves are their own layer so they can LAG behind the fruit as it
# accelerates and catch up as it settles - momentum, as in Brian's original.
LOGO_LAYER_LEAVES = "logo-leaves.png"
LOGO_LAYER_FRUIT = "logo-fruit.png"
POWER_ON_FILENAME = "power_on.mp4"
POWER_OFF_FILENAME = "power_off.mp4"
GLITCH_FILENAME = "glitch.mp4"

# The bundled retro OSD font, used for the placeholder ident.
FONTS_DIR = DEFAULT_ASSETS_DIR / "fonts"


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


@lru_cache(maxsize=1)
def drawtext_available() -> bool:
    """Whether this ffmpeg can render text (needs libfreetype).

    Debian's build on the Pi can; Homebrew's on a Mac often cannot. Worth
    checking rather than discovering through a non-zero exit buried in
    install.sh, where the error would be swallowed by `|| echo "skipped"`.
    """
    if not ffmpeg_available():
        return False
    try:
        out = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"],
            check=False, capture_output=True, text=True, timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return " drawtext " in out.stdout


def _run(cmd: List[str]) -> None:
    log.info("running: %s", " ".join(cmd))
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def generate_static(
    out_path: Path,
    *,
    duration: float = 1.0,
    width: int = 1280,
    height: int = 720,
    fps: int = 25,
) -> Path:
    """Render a loopable, silent analog-snow clip to ``out_path``.

    Only ~0.5s is shown per channel change, but we render a full second so the
    brief loop never shows a visible seam. The clip has no audio track, so
    channel changes are silent (no static hiss).
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"nullsrc=s={width}x{height}:r={fps}:d={duration}",
        "-vf", "geq=lum='random(1)*255':cb=128:cr=128,format=yuv420p",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        # Silent: the snow is picture-only, no audio hiss.
        "-an",
        str(out_path),
    ]
    _run(cmd)
    return out_path


def generate_glitch(
    out_path: Path,
    *,
    duration: float = 0.6,
    width: int = 1280,
    height: int = 720,
    fps: int = 25,
) -> Path:
    """Render a short, silent 'digital glitch' clip to ``out_path``.

    Chunky coloured blocks (small random frame scaled up with nearest-neighbour)
    read as corrupted video macroblocks - a brief digital glitch shown while the
    channel changes. Only a fraction is shown per change, but the CRT shader is
    applied to it so it stays inside the tube frame.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"nullsrc=s=96x54:r={fps}:d={duration}",
        "-vf", (
            "geq=r='random(1)*255':g='random(2)*255':b='random(3)*255',"
            f"scale={width}:{height}:flags=neighbor,format=yuv420p"
        ),
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-an",
        str(out_path),
    ]
    _run(cmd)
    return out_path


def generate_color_bars(
    out_path: Path,
    *,
    duration: float = 6.0,
    width: int = 1280,
    height: int = 720,
    fps: int = 25,
) -> Path:
    """Render SMPTE colour bars with a 1 kHz tone to ``out_path``."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"smptehdbars=s={width}x{height}:r={fps}:d={duration}",
        "-f", "lavfi",
        "-i", f"sine=frequency=1000:duration={duration}:sample_rate=48000",
        "-af", "volume=0.1",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "96k",
        "-shortest",
        str(out_path),
    ]
    _run(cmd)
    return out_path


def _ident_command(
    out_path: Path,
    glyphs: list,
    circle: Path,
    leaves: Optional[Path],
    *,
    width: int,
    height: int,
    fps: int,
    duration: float,
) -> list:
    """Build the ffmpeg command for the ident.

    ONE ffmpeg pass, not a frame at a time: the animation is pure horizontal
    translation and overlay's x accepts an expression in ``t``. Far faster to
    render and far easier to retime.

    The motion:

    * Every letter starts behind the fruit and slides out to its place at
      CONSTANT SIZE - never scaling, never fading.
    * Positions are relative to where the fruit is AT THAT INSTANT, so letters
      keep emerging from behind it even while it is itself moving.
    * A black bar the width of the fruit sits between the letters and the fruit.
      It is invisible against the black background, and it is what actually
      hides a letter until it has genuinely slid clear. Without it a tall letter
      like the b pops into view while still centred on the fruit, because its
      ascender is taller than the fruit is wide.
    * The easing OVERSHOOTS slightly and settles back, so the letters carry
      momentum rather than gliding to a dead stop.
    * The leaves lag the fruit by a fraction of a second, so they trail as it
      accelerates and catch up as it lands.
    """
    raw_w, raw_h = _png_size(circle)
    base = (width * 0.76) / raw_w
    lw, lh = max(2, int(raw_w * base)), max(2, int(raw_h * base))
    lock_x, lock_y = (width - lw) // 2, (height - lh) // 2
    cx0, _cy0 = _png_opaque_centre(circle)
    fruit_cx = cx0 * base
    fruit_dia = _png_opaque_width(circle) * base
    start_cx = width / 2

    t_alone = duration * 0.12
    t_end = duration * 0.64
    lag = duration * 0.035              # how far the leaves trail the fruit

    centres = [_png_opaque_centre(g)[0] * base for g in glyphs]
    order = sorted(range(len(glyphs)), key=lambda i: -abs(centres[i] - fruit_cx))
    starts = {gi: t_alone + n * (duration * 0.022) for n, gi in enumerate(order)}

    def ease(t_expr: str, t0: float, t1: float) -> str:
        """easeOutBack: overshoots the target, then settles - the rubberband.

        Written with explicit multiplication rather than pow(), because pow()
        with a negative base is asking for trouble.
        """
        p = f"clip(({t_expr}-{t0:.3f})/{max(0.01, t1 - t0):.3f},0,1)"
        u = f"({p}-1)"
        return f"(1+2.70158*{u}*{u}*{u}+1.70158*{u}*{u})"

    fruit_final_cx = lock_x + fruit_cx
    ef = ease("t", t_alone, t_end)
    fx_now = f"({start_cx:.1f}+({fruit_final_cx:.1f}-{start_cx:.1f})*{ef})"
    ef_lag = ease("t", t_alone + lag, t_end + lag)
    fx_lag = f"({start_cx:.1f}+({fruit_final_cx:.1f}-{start_cx:.1f})*{ef_lag})"

    inputs = ["-f", "lavfi", "-i", f"color=black:s={width}x{height}:r={fps}:d={duration}"]
    for g in glyphs:
        inputs += ["-loop", "1", "-t", str(duration), "-i", str(g)]
    inputs += ["-f", "lavfi", "-i",
               f"color=black:s={max(2,int(fruit_dia))}x{height}:r={fps}:d={duration}"]
    inputs += ["-loop", "1", "-t", str(duration), "-i", str(circle)]
    if leaves is not None:
        inputs += ["-loop", "1", "-t", str(duration), "-i", str(leaves)]

    steps = []
    prev = "0:v"
    for gi, _ in enumerate(glyphs):
        e = ease("t", starts[gi], t_end)
        offset = centres[gi] - fruit_cx
        x = f"({fx_now}+({offset:.1f})*{e}-{centres[gi]:.1f})"
        lbl = f"s{gi}"
        steps.append(
            f"[{gi+1}:v]scale={lw}:{lh}[g{gi}];"
            f"[{prev}][g{gi}]overlay=x='{x}':y={lock_y}[{lbl}]"
        )
        prev = lbl

    bar_i = len(glyphs) + 1
    steps.append(
        f"[{prev}][{bar_i}:v]overlay=x='({fx_now}-{fruit_dia/2:.1f})':y=0[masked]"
    )
    steps.append(
        f"[{bar_i+1}:v]scale={lw}:{lh}[circ];"
        f"[masked][circ]overlay=x='({fx_now}-{fruit_cx:.1f})':y={lock_y}"
        + ("[withfruit]" if leaves is not None else "")
    )
    if leaves is not None:
        steps.append(
            f"[{bar_i+2}:v]scale={lw}:{lh}[lv];"
            f"[withfruit][lv]overlay=x='({fx_lag}-{fruit_cx:.1f})':y={lock_y}"
        )

    return (
        ["ffmpeg", "-y", "-v", "error"]
        + inputs
        + ["-filter_complex", ";".join(steps),
           "-c:v", "libx264", "-preset", "slow", "-crf", "16",
           "-pix_fmt", "yuv420p", "-an", str(out_path)]
    )


def _png_opaque_width(path: Path) -> float:
    """Width of a PNG's opaque pixels."""
    import subprocess as sp

    w, _h = _png_size(path)
    raw = sp.run(
        ["ffmpeg", "-v", "error", "-i", str(path),
         "-vf", "alphaextract,format=gray", "-f", "rawvideo", "-"],
        capture_output=True, check=True,
    ).stdout
    xs = [i % w for i, v in enumerate(raw) if v > 40]
    return (max(xs) - min(xs) + 1) if xs else w


def _png_size(path: Path) -> tuple:
    """Width and height straight from the PNG header."""
    import struct

    data = path.read_bytes()[:33]
    w, h = struct.unpack(">II", data[16:24])
    return w, h


def _png_opaque_centre(path: Path) -> tuple:
    """Centre of a PNG's opaque pixels, via ffmpeg's cropdetect on its alpha."""
    import subprocess as sp

    w, h = _png_size(path)
    raw = sp.run(
        ["ffmpeg", "-v", "error", "-i", str(path),
         "-vf", "alphaextract,format=gray", "-f", "rawvideo", "-"],
        capture_output=True, check=True,
    ).stdout
    xs = [i % w for i, v in enumerate(raw) if v > 40]
    ys = [i // w for i, v in enumerate(raw) if v > 40]
    if not xs:
        return w / 2, h / 2
    return (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2


def generate_logo(
    out_path: Path,
    *,
    text: str = "TANGBOX",
    duration: float = 5.0,
    width: int = 1920,
    height: int = 1080,
    fps: int = 60,
    color: str = "0x4DFF5A",
    image: Optional[Path] = None,
) -> Path:
    """The station ident, played after the switch-on zap.

    Three tiers, each falling back to the next, because this runs before any
    television happens and a missing file must never mean a black screen:

      1. ``logo-g*.png`` + ``logo-circle.png``   -> Brian's ANIMATED ident
      2. ``logo.png``                            -> the wordmark, fading up
      3. nothing                                 -> "TANGBOX" in phosphor green

    5 seconds by Brian's choice - "fine to teach kids to wait". Silent by his
    choice too: it plays every single time the box is switched on. Any button
    press skips the whole sign-on regardless.

    To use a finished animation instead, drop your own ``logo.mp4`` into the
    assets folder. generate_all() only fills in what is missing and will not
    overwrite it, even under --force.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    circle = out_path.parent / LOGO_LAYER_CIRCLE
    leaves = out_path.parent / LOGO_LAYER_LEAVES
    glyphs = sorted(out_path.parent.glob(f"{LOGO_GLYPH_PREFIX}*.png"))
    fade_out_at = max(0.0, duration - 0.5)

    if glyphs and circle.is_file():
        _run(_ident_command(
            out_path, glyphs, circle,
            leaves if leaves.is_file() else None,
            width=width, height=height, fps=fps, duration=duration,
        ))
        return out_path

    image = image if image is not None else out_path.parent / LOGO_IMAGE_FILENAME
    if image.is_file():
        overlay_w = int(width * 0.62)
        _run([
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:r={fps}:d={duration}",
            "-loop", "1", "-t", str(duration), "-i", str(image),
            "-filter_complex",
            f"[1:v]scale={overlay_w}:-1[lg];"
            f"[0:v][lg]overlay=(W-w)/2:(H-h)/2:format=auto,"
            f"fade=t=in:st=0:d=0.5,fade=t=out:st={fade_out_at:.2f}:d=0.5,format=yuv420p",
            "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-an",
            str(out_path),
        ])
        return out_path

    log.info("no logo artwork found; drawing a placeholder ident")
    fade = f"fade=t=in:st=0:d=0.5,fade=t=out:st={fade_out_at:.2f}:d=0.5"
    if drawtext_available():
        font = FONTS_DIR / "VT323-Regular.ttf"
        draw = (
            f"drawtext=text='{text}':fontcolor={color}:fontsize={height // 6}"
            f":x=(w-text_w)/2:y=(h-text_h)/2"
        )
        if font.is_file():
            draw += f":fontfile='{font}'"
        vf = f"{draw},{fade}"
        source = f"color=c=black:s={width}x{height}:r={fps}:d={duration}"
    else:
        vf = fade
        source = f"color=c={color.replace('0x', '#')}:s={width}x{height}:r={fps}:d={duration}"
    _run([
        "ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", source, "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", "-an",
        str(out_path),
    ])
    return out_path


def _radial_frame(
    t: float, radius_of, brightness_of, width: int, height: int
) -> bytes:
    """One frame of a radial zap: a white disc on black, antialiased.

    Built row by row. A circle covers each row as a single span, so the interior
    is one solid fill and only the two edge bands need per-pixel coverage - which
    is what makes 1920x1080 generatable in plain Python at all. Doing the float
    work across the whole row was ~270 million operations per clip and far too
    slow.

    Vertically supersampled 4x: near the top and bottom of the disc the span
    width changes quickly, and integer rows alone read as steps.
    """
    import math

    r = radius_of(t)
    v = max(0, min(255, int(255 * brightness_of(t))))
    cx, cy = width / 2.0, height / 2.0
    black_row = b"\x00" * (width * 3)
    solid_px = bytes((v, v, v))
    rows = []
    for y in range(height):
        widths = []
        for sub in range(4):
            dy = (y + (sub + 0.5) / 4) - cy
            widths.append(math.sqrt(max(0.0, r * r - dy * dy)))
        wmax = max(widths)
        if wmax <= 0.0 or v == 0:
            rows.append(black_row)
            continue
        wmin = min(widths)
        lo = max(0, int(math.floor(cx - wmax)))
        hi = min(width - 1, int(math.ceil(cx + wmax)))
        s_lo = max(lo, int(math.ceil(cx - wmin)) + 1)
        s_hi = min(hi, int(math.floor(cx + wmin)) - 1)

        parts = [b"\x00" * (lo * 3)]
        edge_end = s_lo if s_hi >= s_lo else hi + 1
        for x in range(lo, edge_end):
            cover = 0.0
            for w in widths:
                cover += max(0.0, min(x + 1, cx + w) - max(x, cx - w))
            cover = min(1.0, cover / 4.0)
            val = int(v * cover)
            parts.append(bytes((val, val, val)))
        if s_hi >= s_lo:
            parts.append(solid_px * (s_hi - s_lo + 1))
            for x in range(s_hi + 1, hi + 1):
                cover = 0.0
                for w in widths:
                    cover += max(0.0, min(x + 1, cx + w) - max(x, cx - w))
                cover = min(1.0, cover / 4.0)
                val = int(v * cover)
                parts.append(bytes((val, val, val)))
        parts.append(b"\x00" * ((width - 1 - hi) * 3))
        rows.append(b"".join(parts))
    return b"".join(rows)


def _encode_frames(out_path: Path, frames, width: int, height: int, fps: int) -> Path:
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{width}x{height}", "-r", str(fps),
        "-i", "-",
        # A hard-edged white shape on black is the worst case for compression,
        # and these are under a second, so quality costs almost nothing here.
        "-c:v", "libx264", "-preset", "slow", "-crf", "16",
        "-pix_fmt", "yuv420p", "-an",
        str(out_path),
    ]
    log.info("running: %s", " ".join(cmd))
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for f in frames:
            proc.stdin.write(f)
    finally:
        proc.stdin.close()
        proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed generating {out_path}")
    return out_path


def generate_power_on(
    out_path: Path,
    *,
    duration: float = 0.75,
    width: int = 1920,
    height: int = 1080,
    fps: int = 60,
    lead_in: float = 0.10,
) -> Path:
    """The switch-on: a point of light bursts outward and fills the screen.

    RADIAL, not the older collapse-to-a-horizontal-line. Both are real CRT
    behaviours; Brian preferred the quicker radial pop.

    1920x1080 to match the mode mpv sets, so nothing is scaled up - a hard-edged
    white disc is the worst possible content for an upscale.

    Ends on black so the ident can fade up cleanly behind it.
    """
    import math

    out_path.parent.mkdir(parents=True, exist_ok=True)
    full = math.hypot(width / 2.0, height / 2.0)
    body = duration - lead_in
    t_grow, t_fade = body * 0.68, body * 0.74

    def radius(t):
        t -= lead_in                      # hold on black while mpv gets going
        if t <= 0:
            return 0.0
        if t >= t_grow:
            return full
        # Gentle ease-out. The old 0.55 exponent moved most of the way in the
        # first few frames, which is what read as stepping - the frame RATE was
        # never the problem, the distance per frame was.
        return full * (t / t_grow) ** 0.78

    def bright(t):
        t -= lead_in
        if t < t_fade:
            return 1.0
        return max(0.0, 1.0 - (t - t_fade) / (body - t_fade))

    frames = (
        _radial_frame(i / fps, radius, bright, width, height)
        for i in range(int(duration * fps))
    )
    return _encode_frames(out_path, frames, width, height, fps)


def generate_power_off(
    out_path: Path,
    *,
    duration: float = 0.75,
    width: int = 1920,
    height: int = 1080,
    fps: int = 60,
    lead_in: float = 0.08,
) -> Path:
    """The switch-off: the picture rushes inward to a point, then winks out.

    The mirror of the switch-on. It closes all the way to nothing at the centre
    rather than leaving a dot to fade: the geometry does the disappearing, so
    brightness is constant the whole way down.
    """
    import math

    out_path.parent.mkdir(parents=True, exist_ok=True)
    full = math.hypot(width / 2.0, height / 2.0)
    body = duration - lead_in
    t_shrink = body * 0.85              # then black for what remains

    def radius(t):
        t -= lead_in                      # a beat of full picture before it goes
        if t <= 0:
            return full
        if t >= t_shrink:
            return 0.0
        p = t / t_shrink
        # Closes all the way to nothing, DECELERATING as it goes. An exponent
        # below 1 accelerates into the finish: the first version used 0.85 and
        # spent only 3 frames (50ms) at small sizes, cutting out while still
        # ~6% of the screen wide. It reached zero, but you could not see it
        # arrive. Above 1 the tail stretches instead - 1.5 gives ~9 frames of
        # visible convergence and still reaches a single pixel.
        return full * (1.0 - p) ** 1.5

    def bright(t):
        return 1.0

    frames = (
        _radial_frame(i / fps, radius, bright, width, height)
        for i in range(int(duration * fps))
    )
    return _encode_frames(out_path, frames, width, height, fps)


def generate_all(assets_dir: Path, *, force: bool = False) -> List[Path]:
    """Generate any missing assets in ``assets_dir``; return what exists."""
    if not ffmpeg_available():
        raise RuntimeError(
            "ffmpeg is required to generate assets. Install it with "
            "`sudo apt install ffmpeg`."
        )
    assets_dir.mkdir(parents=True, exist_ok=True)
    results: List[Path] = []

    static_path = assets_dir / STATIC_FILENAME
    if force or not static_path.exists():
        results.append(generate_static(static_path))
    else:
        results.append(static_path)

    glitch_path = assets_dir / GLITCH_FILENAME
    if force or not glitch_path.exists():
        results.append(generate_glitch(glitch_path))
    else:
        results.append(glitch_path)

    bars_path = assets_dir / COLORBARS_FILENAME
    if force or not bars_path.exists():
        results.append(generate_color_bars(bars_path))
    else:
        results.append(bars_path)

    # NOTE: deliberately NOT regenerated under `force`. Everything else here is
    # synthetic and disposable; logo.mp4 is the one asset a person may have
    # replaced with real artwork, and `--force` must not overwrite it.
    logo_path = assets_dir / LOGO_FILENAME
    if not logo_path.exists():
        results.append(generate_logo(logo_path))
    else:
        results.append(logo_path)

    # Also spared by `force`, on the same rule as the logo: never regenerate
    # something a person may have replaced with their own.
    zap_path = assets_dir / POWER_ON_FILENAME
    if not zap_path.exists():
        results.append(generate_power_on(zap_path))
    else:
        results.append(zap_path)

    off_path = assets_dir / POWER_OFF_FILENAME
    if not off_path.exists():
        results.append(generate_power_off(off_path))
    else:
        results.append(off_path)

    return results


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate TangBox filler assets.")
    parser.add_argument(
        "--assets-dir",
        type=Path,
        default=DEFAULT_ASSETS_DIR,
        help=f"where to write the assets (default: {DEFAULT_ASSETS_DIR})",
    )
    parser.add_argument("--force", action="store_true", help="regenerate even if present")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        produced = generate_all(args.assets_dir, force=args.force)
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        log.error("asset generation failed: %s", exc)
        return 1
    for path in produced:
        log.info("asset ready: %s", path)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
