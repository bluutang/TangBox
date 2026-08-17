#!/usr/bin/env python3
"""Print what the box would broadcast, without needing a screen.

Useful because there is no video preview on a Mac: libmpv driven from Python
cannot create a window on macOS (it needs a Cocoa event loop on the main thread,
which the `mpv` command sets up for itself and a plain Python process does not).
On the Pi this is moot - there libmpv draws straight to the framebuffer.

So instead of watching, you read. This runs the real application against a mock
player and prints the running order: which episode, which adverts, in which
order, on which channel. Every decision is made by the same code that runs on
the television; only the drawing is missing.

    scripts/simulate.py                          # 20 items from config.yaml
    scripts/simulate.py --config config.pi.yaml  # check the Pi's lineup
    scripts/simulate.py --steps 40 --seed 1      # a longer, repeatable run
    scripts/simulate.py --channel-up-at 5        # flip channels part-way

Exits non-zero if the lineup has no episodes at all, so it is also a quick
"did I point this at the right folders?" check.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

# Allow running straight from a checkout without installing.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nostalgiabox.actions import Action, InputEvent  # noqa: E402
from nostalgiabox.app import TVApp  # noqa: E402
from nostalgiabox.config import ConfigError, load_config  # noqa: E402
from nostalgiabox.input.manager import InputManager  # noqa: E402
from nostalgiabox.player import END_EOF, MockPlayer  # noqa: E402


def describe(app: TVApp, commercials_root: Optional[Path]) -> str:
    """One line for whatever is on screen right now."""
    path = app._playing_path
    if path is None:
        channel = app.lineup.current
        return f"  --    (no signal)          [CH {channel.number} {channel.name}]"

    is_ad = commercials_root is not None and commercials_root in path.parents
    if is_ad:
        return f"  AD    {path.stem}"
    channel = app.lineup.current
    return f"  SHOW  {path.stem:<28} [CH {channel.number} {channel.name}]"


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="simulate.py",
        description="Print the running order the box would broadcast.",
    )
    parser.add_argument("-c", "--config", default="config.yaml", help="config file")
    parser.add_argument("-n", "--steps", type=int, default=20, help="items to print")
    parser.add_argument("--seed", type=int, help="fix the shuffle for a repeatable run")
    parser.add_argument(
        "--channel-up-at",
        type=int,
        metavar="N",
        help="press channel-up before item N, to check breaks don't carry over",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")

    try:
        config = load_config(args.config)
    except ConfigError as exc:
        print(f"configuration error: {exc}", file=sys.stderr)
        return 2

    if args.seed is not None:
        config = config.__class__(**{**config.__dict__, "shuffle_seed": args.seed})

    app = TVApp(config, MockPlayer(), InputManager([]))
    commercials_root = config.commercials.path

    if not any(not ch.is_empty for ch in app.lineup):
        print("no episodes found on any channel - check the paths in your config.",
              file=sys.stderr)
        return 1

    print(f"config      : {args.config}")
    print(f"tune-in     : {config.tune_in}")
    if app.commercials.is_available:
        print(f"commercials : {len(app.commercials)} clips, "
              f"~{config.commercials.break_seconds:.0f}s per break")
    else:
        print("commercials : none (no breaks)")
    print()

    app.start()
    print(describe(app, commercials_root))

    for i in range(1, args.steps):
        if args.channel_up_at is not None and i == args.channel_up_at:
            print("  >>>   viewer presses CHANNEL UP")
            app.handle_event(InputEvent(Action.CHANNEL_UP))
        else:
            app._ended.put(END_EOF)
            app.step()
        print(describe(app, commercials_root))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
