"""Finding the picture that belongs to a show, and fitting it to a tile.

The channel guide draws a tile per channel. Neither child in this house can
read, so the picture is the only part of that tile they can use.

A show's picture lives in the show's own folder:

    <channel>/<show>/tile.jpg

which is the layout :func:`nostalgiabox.channel.show_name_for` already assumes.
Keeping it there means it travels with the media - copy a show to a new drive
and its picture goes too - and there is no name in a config file that can drift
out of step with a folder on disk.

Nothing here opens an image. Pillow is a Pi-only dependency and this module is
imported by tests that run on a laptop without it, so the actual pixels are
handled in :class:`~nostalgiabox.player.MpvPlayer`. What lives here is the part
worth testing anywhere: which file, and which part of it.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Optional, Tuple

from .channel import show_name_for

# Checked in order, so a JPEG wins if somebody leaves both behind.
TILE_FILENAMES: Tuple[str, ...] = ("tile.jpg", "tile.png")


def tile_image_for(episode: Path, channel_root: Path) -> Optional[Path]:
    """The picture for whichever show ``episode`` belongs to, or None.

    None whenever there is nothing to point at: a show with no picture yet, an
    episode sitting loose in the channel folder with no show around it, or a
    path from somewhere else entirely (an advert). The tile then draws its old
    way instead, which is what lets pictures be added one show at a time
    rather than needing all fifty before anything works.
    """
    show = show_name_for(episode, channel_root)
    if show is None:
        return None
    return _first_existing(channel_root / show)


@lru_cache(maxsize=256)
def _first_existing(show_dir: Path) -> Optional[Path]:
    """The first of :data:`TILE_FILENAMES` present in ``show_dir``.

    Cached because the guide asks this for every visible tile on every redraw,
    and the answer changes only when somebody adds a file to the USB drive.
    """
    for name in TILE_FILENAMES:
        candidate = show_dir / name
        if candidate.is_file():
            return candidate
    return None


def crop_box(
    src_w: int, src_h: int, dst_w: int, dst_h: int
) -> Tuple[int, int, int, int]:
    """The ``(left, top, right, bottom)`` of the source to keep, cropping to fill.

    The tile picture is 4:3. Artwork that is not gets its sides, or its top and
    bottom, trimmed evenly rather than being letterboxed: a tile is small
    enough already without spending part of it on black bars.
    """
    src_ratio = src_w / src_h
    dst_ratio = dst_w / dst_h
    if src_ratio > dst_ratio:
        # Too wide: keep the full height and trim the sides.
        keep_w = round(src_h * dst_ratio)
        left = (src_w - keep_w) // 2
        return (left, 0, left + keep_w, src_h)
    # Too tall, or an exact match: keep the full width and trim top and bottom.
    keep_h = round(src_w / dst_ratio)
    top = (src_h - keep_h) // 2
    return (0, top, src_w, top + keep_h)
