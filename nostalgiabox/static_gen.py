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


def generate_logo(
    out_path: Path,
    *,
    text: str = "TANGBOX",
    duration: float = 2.5,
    width: int = 1920,
    height: int = 1080,
    fps: int = 60,
    color: str = "0x4DFF5A",
    image: Optional[Path] = None,
) -> Path:
    """The station ident, played after the switch-on zap.

    Uses ``logo.png`` (Brian's wordmark, white on transparent) when it is there,
    and falls back to drawing the name in phosphor green when it is not. The
    fallback matters: this runs before any television happens, and a missing
    file must never mean a black screen.

    2.5 seconds on purpose. It plays EVERY time the box is switched on, in front
    of small children who want cartoons, so it is kept short - and any button
    press skips the whole sign-on anyway.

    To replace it with an animation, drop your own ``logo.mp4`` into the assets
    folder: generate_all() only fills in what is missing, and deliberately will
    not overwrite it even under --force.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image = image if image is not None else out_path.parent / LOGO_IMAGE_FILENAME
    fade_out_at = max(0.0, duration - 0.5)

    if image.is_file():
        # Centre it at ~62% of the frame width, on black, fading up and out.
        overlay_w = int(width * 0.62)
        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:r={fps}:d={duration}",
            "-loop", "1", "-t", str(duration), "-i", str(image),
            "-filter_complex",
            f"[1:v]scale={overlay_w}:-1[lg];"
            f"[0:v][lg]overlay=(W-w)/2:(H-h)/2:format=auto,"
            f"fade=t=in:st=0:d=0.5,fade=t=out:st={fade_out_at:.2f}:d=0.5,format=yuv420p",
            "-c:v", "libx264", "-preset", "slow", "-crf", "16", "-an",
            str(out_path),
        ]
        _run(cmd)
        return out_path

    log.info("%s not found; drawing a placeholder ident", image)
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
        log.info("ffmpeg has no drawtext filter; rendering a plain ident card")
        vf = fade
        source = f"color=c={color.replace('0x', '#')}:s={width}x{height}:r={fps}:d={duration}"

    _run([
        "ffmpeg", "-y", "-v", "error",
        "-f", "lavfi", "-i", source,
        "-vf", vf,
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
    duration: float = 0.95,
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
    duration: float = 1.15,
    width: int = 1920,
    height: int = 1080,
    fps: int = 60,
    lead_in: float = 0.08,
) -> Path:
    """The switch-off: the picture rushes inward to a point, then winks out.

    The mirror of the switch-on, and slightly slower - the lingering dot is the
    part everyone remembers, so it is given time to be seen.
    """
    import math

    out_path.parent.mkdir(parents=True, exist_ok=True)
    full = math.hypot(width / 2.0, height / 2.0)
    dot = max(3.0, width / 260.0)
    body = duration - lead_in
    t_shrink, t_hold = body * 0.58, body * 0.78

    def radius(t):
        t -= lead_in                      # a beat of full picture before it goes
        if t <= 0:
            return full
        if t >= t_shrink:
            return dot
        p = t / t_shrink
        # Gentler than the old 0.65: the collapse still accelerates, but no
        # single frame crosses a quarter of the screen.
        return dot + (full - dot) * (1.0 - p) ** 0.85

    def bright(t):
        t -= lead_in
        if t < t_hold:
            return 1.0
        return max(0.0, 1.0 - (t - t_hold) / (body - t_hold))

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
