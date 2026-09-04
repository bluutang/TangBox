"""Best-effort media duration probing via ffprobe, with an on-disk cache.

Only the "broadcast" tune-in mode needs to know how long each episode runs (so
it can pretend the channel has been airing continuously). Probing is entirely
best-effort: if ffprobe is missing or a file cannot be read, we fall back to an
assumed episode length so the box still works.

🔴 WHY THE CACHE EXISTS. Every channel is `broadcast`, and building a channel's
schedule probes EVERY episode on it - synchronously, on the main loop, the
first time anybody tunes there. Measured on the Pi with the library on USB:
**117 ms per probe, 493 episodes on the Anime channel, 57.6 seconds of blocked
main loop.** Input is read on a separate thread and queued, so presses did not
vanish; they piled up and then all fired at once when the storm finished. That
is exactly what Brian reported - "nothing happened for a little bit, then all
the actions cascaded onscreen" - and it was invisible until the USB drive
arrived, because empty channels return early and never build a schedule.

Durations never change for a file that has not changed, so this is cached to
disk and the storm happens once ever rather than once per boot. Entries are
keyed by path and validated against size + mtime, so re-encoding a file (as
happened to 22 of them) correctly invalidates its entry.

The cache lives on the SD card, NOT beside the media: the library drive is
mounted read-only on purpose.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Optional

# A typical kids' TV episode is about 22 minutes; used when we cannot probe.
DEFAULT_EPISODE_SECONDS = 22 * 60.0

CACHE_PATH = Path.home() / ".cache" / "tangbox" / "durations.json"

_cache: Optional[Dict[str, list]] = None
_dirty = False

# New entries probed since the last write. Batched so a lazy caller probing one
# file at a time still persists, without writing the whole cache 146 times.
_since_flush = 0
_FLUSH_EVERY = 20


def _load_cache() -> Dict[str, list]:
    """Read the cache once per process. Any failure just means an empty cache."""
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(CACHE_PATH.read_text())
            if not isinstance(_cache, dict):
                _cache = {}
        except Exception:  # noqa: BLE001 - a bad cache must never stop playback
            _cache = {}
    return _cache


def _stat_key(path: Path):
    """Size and mtime, so a changed file does not keep a stale duration."""
    try:
        st = path.stat()
        return [st.st_size, int(st.st_mtime)]
    except OSError:
        return None


def flush_cache() -> None:
    """Write the cache out if anything new was probed.

    Called after a channel finishes building its schedule rather than after
    every probe - one write per channel instead of hundreds. Written via a
    temporary file and replaced atomically, so an interrupted write cannot
    leave a corrupt cache behind.
    """
    global _dirty, _since_flush
    _since_flush = 0
    if not _dirty or _cache is None:
        return
    try:
        CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(CACHE_PATH.parent), suffix=".tmp")
        with os.fdopen(fd, "w") as fh:
            json.dump(_cache, fh)
        os.replace(tmp, CACHE_PATH)
        _dirty = False
    except Exception:  # noqa: BLE001 - failing to cache is not worth a crash
        pass


def ffprobe_available() -> bool:
    return shutil.which("ffprobe") is not None


def probe_duration(path: Path, *, timeout: float = 15.0) -> Optional[float]:
    """Return the duration of ``path`` in seconds, or ``None`` on failure.

    Consults the on-disk cache first; a hit costs no subprocess at all.
    """
    global _dirty
    key = str(path)
    stat = _stat_key(path)
    cache = _load_cache()
    hit = cache.get(key)
    # [duration, size, mtime] - only trust it if the file is unchanged.
    if hit and stat and len(hit) == 3 and hit[1:] == stat:
        return hit[0]

    value = _probe_uncached(path, timeout=timeout)
    if value is not None and stat is not None:
        cache[key] = [value, stat[0], stat[1]]
        _dirty = True
        # Persist without the caller having to know the cache exists. The
        # channel schedule flushes explicitly after its loop, but the two LAZY
        # callers - interstitial.py drawing a break clip, app.py timing the
        # current episode - probe one file at a time and never flushed, so
        # every advert was re-probed on every boot (~102 ms each, 146 clips).
        # A hitch mid-break is exactly where it would be felt.
        global _since_flush
        _since_flush += 1
        if _since_flush >= _FLUSH_EVERY:
            flush_cache()
    return value


def _probe_uncached(path: Path, *, timeout: float = 15.0) -> Optional[float]:
    if not ffprobe_available():
        return None
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "quiet",
                "-print_format", "json",
                "-show_format",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout or "{}")
        duration = data.get("format", {}).get("duration")
        if duration is None:
            return None
        value = float(duration)
        return value if value > 0 else None
    except (subprocess.SubprocessError, ValueError, OSError):
        return None


__all__ = [
    "probe_duration",
    "ffprobe_available",
    "flush_cache",
    "CACHE_PATH",
    "DEFAULT_EPISODE_SECONDS",
]
