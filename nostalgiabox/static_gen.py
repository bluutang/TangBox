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
from typing import List

log = logging.getLogger(__name__)

# Package-bundled assets live next to this file.
DEFAULT_ASSETS_DIR = Path(__file__).resolve().parent / "assets"

STATIC_FILENAME = "static.mp4"
COLORBARS_FILENAME = "colorbars.mp4"
LOGO_FILENAME = "logo.mp4"
POWER_ON_FILENAME = "power_on.mp4"
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
    duration: float = 3.0,
    width: int = 1280,
    height: int = 720,
    fps: int = 25,
    color: str = "0x4DFF5A",
) -> Path:
    """Render a PLACEHOLDER station ident: the name in phosphor green, fading up.

    This exists so the sign-on sequence works before any artwork does. Replace
    it by dropping a real ``logo.mp4`` into the assets folder - nothing else has
    to change, and generate_all() will leave yours alone because it only fills
    in what is missing.

    Three seconds on purpose. This plays every single time the box is switched
    on, in front of small children who want cartoons; a longer ident is charming
    for about two days.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Fade up from black and back out, so it reads as a station ident rather
    # than a still image someone forgot to remove.
    fade_out_at = max(0.0, duration - 0.6)
    fade = f"fade=t=in:st=0:d=0.6,fade=t=out:st={fade_out_at:.2f}:d=0.6"

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
        # No text renderer. Rather than fail (and be swallowed by install.sh),
        # produce a plain phosphor-green card that fades - still a usable
        # placeholder, and still obviously a placeholder.
        log.info("ffmpeg has no drawtext filter; rendering a plain ident card")
        vf = fade
        source = f"color=c={color.replace('0x', '#')}:s={width}x{height}:r={fps}:d={duration}"

    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", source,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-an",
        str(out_path),
    ]
    _run(cmd)
    return out_path


def generate_power_on(
    out_path: Path,
    *,
    duration: float = 0.75,
    width: int = 1280,
    height: int = 720,
    fps: int = 50,
) -> Path:
    """The CRT switch-on: a dot blooms to a line, the line opens to the frame.

    Frames are built here and piped to ffmpeg as raw pixels rather than
    described as an ffmpeg filter. That is deliberate: `drawbox` takes `t` as
    its THICKNESS option while `t` inside an expression means time, and the
    resulting clip was a solid white rectangle. Generating the pixels is
    completely predictable and needs no filter-syntax guesswork.

    50fps, not the 25 the other assets use - the whole thing lasts under a
    second and the movement is fast, so half the frames look like a stutter.

    Ends on black so the ident can fade up cleanly behind it.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    line_h = 6
    t_widen, t_open, t_fade = 0.16, 0.40, 0.52

    def frame(t: float) -> bytes:
        if t < t_widen:                       # dot -> horizontal line
            w, h, bright = max(2, int(width * (t / t_widen))), line_h, 1.0
        elif t < t_open:                      # line -> full frame
            progress = (t - t_widen) / (t_open - t_widen)
            w = width
            h = max(line_h, int(line_h + (height - line_h) * progress))
            bright = 1.0
        else:                                 # settle to black for the ident
            w, h = width, height
            bright = (
                max(0.0, 1.0 - (t - t_fade) / (duration - t_fade))
                if t >= t_fade
                else 1.0
            )
        value = max(0, min(255, int(255 * bright)))
        x0, y0 = (width - w) // 2, (height - h) // 2
        black_row = b"\x00" * (width * 3)
        lit_row = (
            b"\x00" * (x0 * 3)
            + bytes([value]) * (w * 3)
            + b"\x00" * ((width - x0 - w) * 3)
        )
        return b"".join(
            lit_row if y0 <= y < y0 + h else black_row for y in range(height)
        )

    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "rgb24",
        "-s", f"{width}x{height}", "-r", str(fps),
        "-i", "-",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-an",
        str(out_path),
    ]
    log.info("running: %s", " ".join(cmd))
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    assert proc.stdin is not None
    try:
        for i in range(int(duration * fps)):
            proc.stdin.write(frame(i / fps))
    finally:
        proc.stdin.close()
        proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed generating {out_path}")
    return out_path


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
