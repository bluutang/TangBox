#!/usr/bin/env python3
"""Draw one of the box's overlays to a PNG, on a computer, with no Pi.

Most of what TangBox puts on screen is ASS - the channel banner, the guide, the
volume readout, the sign-off message - and libass renders it perfectly well on a
Mac. So "it cannot be judged without a television" was only ever true of the CRT
shader, which needs a GPU video output. Everything else can be looked at here.

That matters because geometry tests pass on layouts that look wrong. The
episode timeline shipped with 499 green tests and a 112px hole in it, which
nobody could have seen without rendering the thing.

    scripts/render-overlay.py banner --show Pocoyo --episode "El Globo Rojo"
    scripts/render-overlay.py banner --position 492 --runtime 1320   # + timeline
    scripts/render-overlay.py guide --channels 17 --cursor 9
    scripts/render-overlay.py volume --level 40
    scripts/render-overlay.py message --text "CARRY ON"

Writes ./overlay.png unless told otherwise with -o. Pass --background to draw
over a real clip instead of a flat colour; the default flat grey is deliberately
plain so the overlay is what you are judging.

WHAT THIS CANNOT SHOW:

* The CRT picture effect. It is a GLSL shader and runs in the GPU video output;
  the image output used here scales with zimg and ignores shaders silently.
* Guide ARTWORK. The tile pictures are a separate mpv image layer, not ASS, so
  the guide renders with empty tiles. The frames and labels are real.

Needs mpv (which the project already depends on) and, for the default flat
background only, ffmpeg.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Dict, List, Sequence

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from nostalgiabox.config import UiConfig  # noqa: E402
from nostalgiabox.guide import guide_ass  # noqa: E402
from nostalgiabox.overlay import (  # noqa: E402
    CANVAS_H,
    CANVAS_W,
    _channel_bug_ass,
    _message_ass,
    _standby_ass,
    _volume_ass,
)

FONTS_DIR = REPO_ROOT / "nostalgiabox" / "assets" / "fonts"

_HEADER = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {CANVAS_W}
PlayResY: {CANVAS_H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,VT323,40,&H004DFF5A,7,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Text
"""


def ass_document(lines: Sequence[str]) -> str:
    """Wrap already-built ASS drawing lines into a file libass will accept.

    The canvas declared here must match the one overlay.py positions against,
    or every co-ordinate in the box lands somewhere else on screen.
    """
    events = "".join(
        f"Dialogue: 0,0:00:00.00,0:01:00.00,Default,{line}\n"
        for line in lines
        if line.strip()
    )
    return _HEADER + events


# -- the overlays, each returning ASS lines ---------------------------------


def _banner(ui: UiConfig, args: argparse.Namespace) -> str:
    return _channel_bug_ass(
        args.channel,
        args.name,
        ui,
        show=args.show,
        episode=args.episode,
        position=args.position,
        duration=args.runtime,
    )


def _guide(ui: UiConfig, args: argparse.Namespace) -> str:
    channels = [(n + 2, f"Channel {n + 2}") for n in range(args.channels)]
    return guide_ass(channels, args.cursor, ui, on_now=args.on_now)


def _volume(ui: UiConfig, args: argparse.Namespace) -> str:
    return _volume_ass(args.level, args.muted, ui)


def _message(ui: UiConfig, args: argparse.Namespace) -> str:
    return _message_ass(args.text, ui)


def _standby(ui: UiConfig, args: argparse.Namespace) -> str:
    return _standby_ass(ui)


OVERLAYS: Dict[str, Callable[[UiConfig, argparse.Namespace], str]] = {
    "banner": _banner,
    "guide": _guide,
    "volume": _volume,
    "message": _message,
    "standby": _standby,
}


# -- rendering ---------------------------------------------------------------


def flat_background(colour: str, out: Path) -> Path:
    """A plain one-second clip, so the overlay is the only thing to look at."""
    if shutil.which("ffmpeg") is None:
        raise SystemExit(
            "ffmpeg is needed to make the default background.\n"
            "Either install it, or pass --background with a clip of your own."
        )
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", f"color=c={colour}:s={CANVAS_W}x{CANVAS_H}:d=1",
         "-pix_fmt", "yuv420p", str(out)],
        check=True,
    )
    return out


def render(ass: str, background: Path, out: Path) -> Path:
    """Have mpv draw the ASS over the background and save one frame."""
    if shutil.which("mpv") is None:
        raise SystemExit("mpv is not installed; `brew install mpv`.")
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        ass_path = tmpdir / "overlay.ass"
        ass_path.write_text(ass, encoding="utf-8")
        shots = tmpdir / "shots"
        subprocess.run(
            ["mpv", "--no-config", "--really-quiet", str(background),
             f"--sub-file={ass_path}", f"--sub-fonts-dir={FONTS_DIR}",
             "--frames=1", "--vo=image", "--vo-image-format=png",
             f"--vo-image-outdir={shots}"],
            check=True,
        )
        frames = sorted(shots.glob("*.png"))
        if not frames:
            raise SystemExit("mpv wrote no frame; is the background readable?")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(frames[0].read_bytes())
    return out


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    p.add_argument("overlay", choices=sorted(OVERLAYS))
    p.add_argument("-o", "--out", type=Path, default=Path("overlay.png"))
    p.add_argument("--background", type=Path,
                   help="a clip or image to draw over (default: flat grey)")
    p.add_argument("--colour", default="0x2b2f36",
                   help="colour of the default flat background")
    # banner
    p.add_argument("--channel", type=int, default=2)
    p.add_argument("--name", default="Los Pequenos")
    p.add_argument("--show", default="Pocoyo")
    p.add_argument("--episode", default="El Globo Rojo")
    p.add_argument("--position", type=float,
                   help="seconds into the programme (adds the timeline)")
    p.add_argument("--runtime", type=float,
                   help="how long the programme runs (adds the timeline)")
    # guide
    p.add_argument("--channels", type=int, default=17)
    p.add_argument("--cursor", type=int, default=0)
    p.add_argument("--on-now", type=int, default=0)
    # volume
    p.add_argument("--level", type=int, default=60)
    p.add_argument("--muted", action="store_true")
    # message
    p.add_argument("--text", default="GOODBYE")
    args = p.parse_args(argv)

    ui = UiConfig()
    lines = OVERLAYS[args.overlay](ui, args).split("\n")

    with tempfile.TemporaryDirectory() as tmp:
        background = args.background or flat_background(
            args.colour, Path(tmp) / "bg.mp4"
        )
        out = render(ass_document(lines), background, args.out)

    print(f"wrote {out}")
    if args.overlay == "guide":
        print("note: tile artwork is an image layer, not ASS, so tiles are empty here")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
