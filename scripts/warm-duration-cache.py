#!/usr/bin/env python3
"""Pre-warm the on-disk episode-duration cache for every configured channel.

The box measures each episode's length with ffprobe the first time anyone
tunes to its channel (nostalgiabox/probe.py has the full story) and remembers
the answer on disk from then on. A channel that has never been tuned to pays
that cost live, on the TV: the main loop blocks for the length of the probe,
button presses queue up on their own thread, and they all fire at once the
moment it unblocks - "nothing happened, then everything cascaded".

Run this on the Pi any time the library changes - a new show filed, a channel
added or reorganized, episodes re-encoded - so nobody hits that live. It reuses
probe_duration()/flush_cache() directly, so an already-cached, unchanged file
costs nothing to re-check; only new or changed files are actually probed.

    .venv/bin/python3 scripts/warm-duration-cache.py [/path/to/config.yaml]
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nostalgiabox.channel import scan_episodes
from nostalgiabox.config import load_config
from nostalgiabox import probe as probe_mod
from nostalgiabox.probe import flush_cache, probe_duration

DEFAULT_CONFIG = Path("/home/brian/TangBox/config.yaml")


def main() -> int:
    config_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CONFIG
    config = load_config(config_path)

    total = 0
    newly_probed = 0
    failed: list[str] = []
    start = time.monotonic()

    for ch_cfg in config.channels:
        episodes = scan_episodes(
            ch_cfg.path,
            config.video_extensions,
            recursive=config.scan_recursive,
            exclude=ch_cfg.exclude,
            exclude_seasons=ch_cfg.exclude_seasons,
        )
        chan_new = 0
        for ep in episodes:
            total += 1
            # Reuse the module's own cache-hit check for an accurate "was
            # this new" count instead of timing the call, which is fragile.
            cache = probe_mod._load_cache()
            stat = probe_mod._stat_key(ep)
            hit = cache.get(str(ep))
            already_cached = bool(hit and stat and len(hit) == 3 and hit[1:] == stat)

            duration = probe_duration(ep)
            if not already_cached:
                newly_probed += 1
                chan_new += 1
            if duration is None:
                failed.append(str(ep))
        if chan_new:
            print(f"  {ch_cfg.name}: probed {chan_new} new/changed episode(s)")

    flush_cache()
    elapsed = time.monotonic() - start
    print(f"\n{total} episodes checked, {newly_probed} newly probed, "
          f"{len(failed)} failed, {elapsed:.1f}s")
    for f in failed[:10]:
        print(f"  FAILED: {f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
