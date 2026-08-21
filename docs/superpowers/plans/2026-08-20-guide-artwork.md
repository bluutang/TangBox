# Show Artwork on the Guide Tiles — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

> **ALL SEVEN TASKS COMPLETE**, branch `guide-artwork`, 448 tests passing.
> Not yet seen on a television - see the spec's "Only a television can answer these".

**Goal:** Put a picture of the show on each channel-guide tile, so a child who cannot read can choose a channel.

**Architecture:** The guide keeps its ASS text layer and gains a second layer of bitmaps drawn by mpv underneath it. Geometry is computed once by `page_tiles()` and shared by both layers, so the picture and the text it belongs to cannot drift apart. A tile with no picture falls back to exactly today's drawing, which is what makes this safe to ship before any artwork exists.

**Tech Stack:** Python 3, mpv via python-mpv (`overlay_add` / `create_image_overlay`), Pillow for scaling, pytest.

**Spec:** `docs/superpowers/specs/2026-08-20-guide-artwork-design.md`

## Global Constraints

- **Canvas is 1280x720.** All geometry is in canvas pixels; mpv scales to the TV.
- **A tile is 264x288** on a 4x2 page. The picture is the top **264x198** (exactly 4:3), the text band is the remaining **90px**.
- **The picture is the largest 4:3 rectangle that fits above the text band**, centred (`art_rect`). The band is `0.3125` of the tile's height. On the real 264x288 tile that gives exactly 264x198 with a 90px band.
  > Deriving the height from the tile's WIDTH was the first attempt and is WRONG: a one-page lineup gets 552x305 tiles, where a picture as wide as the tile would be 414 tall and overflow.
- **Artwork lives at `<channel>/<show>/tile.jpg`**, with `tile.png` also accepted. `<channel>/<show>/` is the layout `show_name_for()` already assumes.
- **A tile with no artwork draws exactly as it does today.** No visual change to a box with no pictures.
- **Only the channel number sits on the picture**, on a solid dark plate so contrast never depends on the artwork. Show name and `ON NOW` stay in the band below.
- **Non-4:3 artwork is cropped to fill**, centred.
- **Pillow is imported lazily, inside `MpvPlayer` only.** It is a Pi runtime dependency; `pytest` must pass on a Mac without it.
- **Every existing test must keep passing.** 388 at the time of writing.
- Run tests with `.venv/bin/python -m pytest`.

---

### Task 1: Ask a channel what it will play next, without playing it ✅ DONE (`4f3eadf`)

**Files:**
- Modify: `nostalgiabox/playlist.py` (add `ShuffleBag.peek`)
- Modify: `nostalgiabox/channel.py` (add `Channel.peek_next`)
- Test: `tests/test_playlist.py`, `tests/test_channel.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `ShuffleBag.peek() -> T`, `Channel.peek_next() -> Optional[Path]`.

- [x] **Step 1: Write the failing test for the bag**

In `tests/test_playlist.py`:

```python
def test_peek_shows_the_next_item_without_handing_it_out():
    bag = ShuffleBag(["a", "b", "c"], random.Random(1))
    assert bag.peek() == bag.next()


def test_peeking_twice_gives_the_same_answer():
    bag = ShuffleBag(["a", "b", "c"], random.Random(1))
    assert bag.peek() == bag.peek()


def test_peek_refills_an_exhausted_bag_rather_than_failing():
    bag = ShuffleBag(["a", "b"], random.Random(1))
    bag.next()
    bag.next()
    assert bag.peek() in ("a", "b")
```

- [x] **Step 2: Run it and watch it fail**

Run: `.venv/bin/python -m pytest tests/test_playlist.py -k peek -v`
Expected: FAIL, `AttributeError: 'ShuffleBag' object has no attribute 'peek'`

- [x] **Step 3: Implement `peek`**

In `nostalgiabox/playlist.py`, after `next()`:

```python
    def peek(self) -> T:
        """The item :meth:`next` will hand out, without handing it out.

        The guide uses this to show what a channel would play if you tuned to
        it. Refills an exhausted bag exactly as :meth:`next` would, so the
        answer stays true rather than raising at a cycle boundary.
        """
        if not self._items:
            raise IndexError("cannot draw from an empty ShuffleBag")
        if not self._queue:
            self._refill()
        return self._queue[-1]
```

- [x] **Step 4: Run it and watch it pass**

Run: `.venv/bin/python -m pytest tests/test_playlist.py -v`
Expected: PASS

- [x] **Step 5: Write the failing test for the channel**

In `tests/test_channel.py`:

```python
def test_peek_next_names_what_tuning_in_would_play(tmp_path):
    make_show(tmp_path, "dragon", 4)
    channel = build_channel(tmp_path / "dragon", number=2, tune_in="random")
    assert channel.peek_next() == channel.tune_in().path


def test_peek_next_does_not_consume_the_episode(tmp_path):
    make_show(tmp_path, "dragon", 4)
    channel = build_channel(tmp_path / "dragon", number=2, tune_in="random")
    channel.peek_next()
    channel.peek_next()
    assert channel.peek_next() == channel.tune_in().path


def test_peek_next_on_a_resume_channel_names_where_you_left_off(tmp_path):
    make_show(tmp_path, "dragon", 4)
    channel = build_channel(tmp_path / "dragon", number=2, tune_in="resume")
    episode = channel.episodes[0]
    channel.remember(episode, 90.0)
    assert channel.peek_next() == episode


def test_peek_next_on_an_empty_channel_is_none(tmp_path):
    (tmp_path / "empty").mkdir()
    channel = build_channel(tmp_path / "empty", number=2)
    assert channel.peek_next() is None
```

Match the existing helpers in `tests/test_channel.py` for `make_show` / channel
construction; if that file builds channels inline rather than with a helper,
build them the same way inline.

- [x] **Step 6: Run it and watch it fail**

Run: `.venv/bin/python -m pytest tests/test_channel.py -k peek_next -v`
Expected: FAIL, `AttributeError: 'Channel' object has no attribute 'peek_next'`

- [x] **Step 7: Implement `peek_next`**

In `nostalgiabox/channel.py`, directly after `tune_in`:

```python
    def peek_next(self) -> Optional[Path]:
        """Which episode tuning to this channel would play, without playing it.

        The guide asks every channel this so a tile can show the programme you
        would actually GET. It must not disturb anything: no episode is drawn
        from the bag, no resume position is spent, and no broadcast schedule is
        built - building one probes every file with ffprobe, which is far too
        slow to do while somebody is holding a remote.
        """
        if self.is_empty:
            return None
        if self.tune_in_mode == "resume" and self._resume_path is not None:
            return self._resume_path
        if self.tune_in_mode == "broadcast" and self._broadcast is not None:
            return self._broadcast.at(time.time()).path
        assert self._bag is not None
        return self._bag.peek()
```

- [x] **Step 8: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS, 395 tests

- [x] **Step 9: Commit**

```bash
git add nostalgiabox/playlist.py nostalgiabox/channel.py tests/test_playlist.py tests/test_channel.py
git commit -m "A channel can say what it would play, without playing it"
```

---

### Task 2: Find a show's picture on disk ✅ DONE (`bcb3e6f`)

**Files:**
- Create: `nostalgiabox/artwork.py`
- Create: `tests/test_artwork.py`

**Interfaces:**
- Consumes: `show_name_for` from `nostalgiabox.channel`.
- Produces: `tile_image_for(episode: Path, channel_root: Path) -> Optional[Path]`, `crop_box(src_w: int, src_h: int, dst_w: int, dst_h: int) -> Tuple[int, int, int, int]`, `TILE_FILENAMES: Tuple[str, ...]`.

- [x] **Step 1: Write the failing tests**

Create `tests/test_artwork.py`:

```python
"""Finding a show's tile picture, and fitting it to a tile."""

from nostalgiabox.artwork import crop_box, tile_image_for


def _episode(tmp_path, show="Rugrats", season="Season 01"):
    ep = tmp_path / "Nick Jr" / show / season / "ep.mp4"
    ep.parent.mkdir(parents=True)
    ep.touch()
    return ep


def test_a_tile_jpg_beside_the_seasons_is_the_shows_picture(tmp_path):
    episode = _episode(tmp_path)
    art = tmp_path / "Nick Jr" / "Rugrats" / "tile.jpg"
    art.touch()
    assert tile_image_for(episode, tmp_path / "Nick Jr") == art


def test_a_png_is_accepted_too(tmp_path):
    episode = _episode(tmp_path)
    art = tmp_path / "Nick Jr" / "Rugrats" / "tile.png"
    art.touch()
    assert tile_image_for(episode, tmp_path / "Nick Jr") == art


def test_jpg_wins_when_both_are_present(tmp_path):
    episode = _episode(tmp_path)
    (tmp_path / "Nick Jr" / "Rugrats" / "tile.png").touch()
    jpg = tmp_path / "Nick Jr" / "Rugrats" / "tile.jpg"
    jpg.touch()
    assert tile_image_for(episode, tmp_path / "Nick Jr") == jpg


def test_a_show_with_no_picture_is_none(tmp_path):
    episode = _episode(tmp_path)
    assert tile_image_for(episode, tmp_path / "Nick Jr") is None


def test_an_episode_loose_in_the_channel_folder_has_no_show_and_no_picture(tmp_path):
    root = tmp_path / "Nick Jr"
    root.mkdir()
    loose = root / "ep.mp4"
    loose.touch()
    assert tile_image_for(loose, root) is None


def test_an_episode_from_somewhere_else_entirely_is_none(tmp_path):
    # An advert, say. Must not raise.
    episode = _episode(tmp_path)
    assert tile_image_for(episode, tmp_path / "Somewhere Else") is None


# -- fitting a picture to the tile ------------------------------------------
# The tile picture is 4:3. Anything else is cropped to fill, centred, because
# letterbox bars inside a tile this small waste the only space a child can use.


def test_a_four_three_picture_is_not_cropped_at_all():
    assert crop_box(1024, 768, 264, 198) == (0, 0, 1024, 768)


def test_a_widescreen_picture_loses_its_sides():
    # 16:9 into 4:3: full height, centred horizontally.
    left, top, right, bottom = crop_box(1920, 1080, 264, 198)
    assert (top, bottom) == (0, 1080)
    assert right - left == 1440
    assert left == 240 and right == 1680


def test_a_tall_picture_loses_its_top_and_bottom():
    left, top, right, bottom = crop_box(600, 900, 264, 198)
    assert (left, right) == (0, 600)
    assert bottom - top == 450
    assert top == 225 and bottom == 675


def test_the_crop_is_never_bigger_than_the_picture():
    for src_w, src_h in ((100, 100), (1920, 1080), (640, 480), (300, 1200)):
        left, top, right, bottom = crop_box(src_w, src_h, 264, 198)
        assert 0 <= left < right <= src_w
        assert 0 <= top < bottom <= src_h
```

- [x] **Step 2: Run them and watch them fail**

Run: `.venv/bin/python -m pytest tests/test_artwork.py -v`
Expected: FAIL, `ModuleNotFoundError: No module named 'nostalgiabox.artwork'`

- [x] **Step 3: Write the module**

Create `nostalgiabox/artwork.py`:

```python
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
    path from somewhere else entirely (an advert). The tile then draws its
    old way instead, which is what lets pictures be added one show at a time.
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
    """The ``(left, top, right, bottom)`` of ``src`` to keep, cropping to fill.

    The tile picture is 4:3. Artwork that is not gets its sides or its top and
    bottom trimmed, centred, rather than being letterboxed: a tile is small
    enough already without spending part of it on black bars.
    """
    src_ratio = src_w / src_h
    dst_ratio = dst_w / dst_h
    if src_ratio > dst_ratio:
        # Too wide: keep the full height, trim the sides.
        keep_w = round(src_h * dst_ratio)
        left = (src_w - keep_w) // 2
        return (left, 0, left + keep_w, src_h)
    # Too tall (or an exact match): keep the full width, trim top and bottom.
    keep_h = round(src_w / dst_ratio)
    top = (src_h - keep_h) // 2
    return (0, top, src_w, top + keep_h)
```

- [x] **Step 4: Run them and watch them pass**

Run: `.venv/bin/python -m pytest tests/test_artwork.py -v`
Expected: PASS, 11 tests

- [x] **Step 5: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS, 406 tests

- [x] **Step 6: Commit**

```bash
git add nostalgiabox/artwork.py tests/test_artwork.py
git commit -m "Find a show's picture, and work out which part of it fits"
```

---

### Task 3: One source of truth for where a tile sits ✅ DONE (`029c941`)

**Files:**
- Modify: `nostalgiabox/guide.py` (extract `page_tiles`, use it in `guide_ass`)
- Test: `tests/test_guide.py`

**Interfaces:**
- Consumes: `page_shape`, `page_count`, `_MARGIN_X`, `_MARGIN_Y`, `_GAP`, `_DOT_STRIP` — all already in `guide.py`.
- Produces: `TileRect` (NamedTuple with fields `index, x, y, w, h`), `page_tiles(count: int, cursor: int, page_cols: int = DEFAULT_PAGE_COLS, page_rows: int = DEFAULT_PAGE_ROWS) -> List[TileRect]`, `art_rect(tile: TileRect) -> Tuple[float, float, float, float]` returning `(x, y, w, h)`.

**Why this task exists:** the picture layer and the text layer must agree on
where a tile is, to the pixel. Two copies of that arithmetic would drift the
first time anyone changed a margin. This task adds no behaviour: it moves
existing geometry into a function and proves the drawing is unchanged.

- [x] **Step 1: Write the failing tests**

Append to `tests/test_guide.py`:

```python
# -- tile geometry ----------------------------------------------------------
# The picture layer and the text layer share this, so they cannot drift apart.


def test_page_tiles_returns_one_rect_per_visible_tile():
    assert len(page_tiles(17, cursor=0)) == 8


def test_page_tiles_returns_only_the_ragged_last_pages_tiles():
    assert len(page_tiles(17, cursor=16)) == 1


def test_page_tiles_carries_the_lineup_index_not_the_position_on_the_page():
    # Page two's first tile is channel index 8, not 0 - the caller uses this
    # to look up the right channel.
    assert page_tiles(17, cursor=8)[0].index == 8


def test_a_tile_is_264_by_288_on_a_four_by_two_page():
    tile = page_tiles(17, cursor=0)[0]
    assert (round(tile.w), round(tile.h)) == (264, 288)


def test_tiles_do_not_overlap():
    rects = page_tiles(17, cursor=0)
    for a in rects:
        for b in rects:
            if a.index >= b.index:
                continue
            apart = (
                a.x + a.w <= b.x or b.x + b.w <= a.x
                or a.y + a.h <= b.y or b.y + b.h <= a.y
            )
            assert apart, (a, b)


def test_the_picture_is_four_three_whatever_the_tile_is():
    for count, cols, rows in ((17, 4, 2), (17, 5, 3), (30, 3, 2)):
        tile = page_tiles(count, cursor=0, page_cols=cols, page_rows=rows)[0]
        assert abs(_w_over_h(art_rect(tile)) - 4 / 3) < 0.001


def test_the_picture_is_198_tall_on_the_real_box():
    assert (round(art_rect(page_tiles(17, 0)[0])[2]),
            round(art_rect(page_tiles(17, 0)[0])[3])) == (264, 198)
```

Add `TileRect`, `page_tiles` and `art_rect` to the import block at the top of
`tests/test_guide.py`.

- [x] **Step 2: Run them and watch them fail**

Run: `.venv/bin/python -m pytest tests/test_guide.py -k "page_tiles or art_rect or picture_is" -v`
Expected: FAIL, `ImportError: cannot import name 'page_tiles'`

- [x] **Step 3: Add the geometry**

In `nostalgiabox/guide.py`, after `page_count` and before `class Guide`:

```python
class TileRect(NamedTuple):
    """Where one tile sits on the canvas, and which channel it is.

    ``index`` is into the WHOLE lineup, not into the page, so a caller can look
    up the channel without repeating the paging arithmetic.
    """

    index: int
    x: float
    y: float
    w: float
    h: float


_BAND_RATIO = 0.3125   # 90px of a 288px tile
_ART_RATIO = 4 / 3


def art_rect(tile: "TileRect") -> Tuple[float, float, float, float]:
    """``(x, y, w, h)`` of the picture area inside ``tile``.

    The largest 4:3 rectangle that fits above the text band, centred across the
    tile. On the real box - a 264x288 tile - that is exactly 264x198 with a
    90px band, which is what the artwork is cut to.

    It has to be FITTED, not derived from the tile's width: a lineup small
    enough for one page gets 552x305 tiles, and a 4:3 picture as wide as that
    would be 414 tall and burst out of the bottom of the tile.
    """
    h = tile.h * (1 - _BAND_RATIO)
    w = h * _ART_RATIO
    if w > tile.w:
        w = tile.w
        h = w / _ART_RATIO
    return (tile.x + (tile.w - w) / 2, tile.y, w, h)


def page_tiles(
    count: int,
    cursor: int,
    page_cols: int = DEFAULT_PAGE_COLS,
    page_rows: int = DEFAULT_PAGE_ROWS,
) -> List[TileRect]:
    """Where every tile on the cursor's page sits.

    The single source of truth for tile geometry: the text layer draws from
    this and the picture layer is positioned from it, so a picture cannot end
    up a few pixels away from the name underneath it.
    """
    if count <= 0:
        return []
    cols, rows = page_shape(count, page_cols, page_rows)
    pages = page_count(count, page_cols, page_rows)
    per_page = cols * rows
    page = max(0, min(pages - 1, cursor // per_page))
    first = page * per_page
    strip = _DOT_STRIP if pages > 1 else 0
    tile_w = (CANVAS_W - 2 * _MARGIN_X - _GAP * (cols - 1)) / cols
    tile_h = (CANVAS_H - 2 * _MARGIN_Y - strip - _GAP * (rows - 1)) / rows
    rects = []
    for local in range(min(per_page, count - first)):
        col, row = local % cols, local // cols
        rects.append(
            TileRect(
                index=first + local,
                x=_MARGIN_X + col * (tile_w + _GAP),
                y=_MARGIN_Y + row * (tile_h + _GAP),
                w=tile_w,
                h=tile_h,
            )
        )
    return rects
```

Add `NamedTuple` to the `typing` import at the top of the file, and add
`"TileRect"`, `"page_tiles"` and `"art_rect"` to `__all__`.

- [x] **Step 4: Run them and watch them pass**

Run: `.venv/bin/python -m pytest tests/test_guide.py -v`
Expected: PASS

- [x] **Step 5: Make `guide_ass` use it, changing nothing**

In `guide_ass`, replace the geometry block and the `for local, (number, name) in
enumerate(visible):` loop header. Delete these lines:

```python
    per_page = cols * rows
    page = max(0, min(pages - 1, cursor // per_page))
    first = page * per_page
    visible = channels[first:first + per_page]
```

and the `col, row = ...` / `x = ...` / `y = ...` lines inside the loop. Drive
the loop from `page_tiles` instead:

```python
    rects = page_tiles(count, cursor, page_cols, page_rows)
    page = rects[0].index // (cols * rows) if rects else 0
    tile_w = rects[0].w if rects else 0.0
    tile_h = rects[0].h if rects else 0.0
```

and:

```python
    for rect in rects:
        number, name = channels[rect.index]
        x, y = rect.x, rect.y
        cx = x + tile_w / 2
        focused = rect.index == cursor
        alpha = 0 if focused else DIM_ALPHA
```

replacing every later use of `first + local` with `rect.index`.

- [x] **Step 6: Prove the drawing did not change**

This task must be invisible. Run the whole suite:

Run: `.venv/bin/python -m pytest -q`
Expected: PASS, 413 tests. Every existing drawing test passing unchanged IS the
proof — they assert exact positions.

- [x] **Step 7: Commit**

```bash
git add nostalgiabox/guide.py tests/test_guide.py
git commit -m "One source of truth for where a tile sits"
```

---

### Task 4: Draw the tile that has a picture ✅ DONE (`0b8b3c6`)

**Files:**
- Modify: `nostalgiabox/guide.py` (`guide_ass` gains `artwork`, add `_number_plate`)
- Test: `tests/test_guide.py`

**Interfaces:**
- Consumes: `TileRect`, `page_tiles`, `art_rect` from Task 3.
- Produces: `guide_ass(..., artwork: Optional[Sequence[bool]] = None)` — one flag per channel in lineup order, True where that channel's tile has a picture behind it.

**Note:** `guide_ass` takes booleans, not paths. It draws no pictures; it only
lays the text out differently where one will be. The picture itself is Task 6.

- [x] **Step 1: Write the failing tests**

Append to `tests/test_guide.py`:

```python
# -- the tile with a picture ------------------------------------------------
# guide_ass never draws a picture. It is told where one WILL be, and moves the
# text out of the way: the name drops into the band underneath, and the channel
# number shrinks onto a dark plate in the corner.

FOUR_WITH_ART = [True, False, False, False]


def test_a_tile_with_a_picture_puts_its_name_below_the_picture():
    plain = guide_ass(FOUR, cursor=0, ui=_ui())
    arty = guide_ass(FOUR, cursor=0, ui=_ui(), artwork=FOUR_WITH_ART)
    assert _name_y(plain, "Los Pequenos") < _name_y(arty, "Los Pequenos")


def test_the_name_stays_inside_the_tile():
    arty = guide_ass(FOUR, cursor=0, ui=_ui(), artwork=FOUR_WITH_ART)
    tile = page_tiles(len(FOUR), cursor=0)[0]
    assert _name_y(arty, "Los Pequenos") < tile.y + tile.h


def test_a_tile_with_no_picture_is_drawn_exactly_as_before():
    # The whole reason this is safe to ship before any artwork exists.
    none = [False, False, False, False]
    assert guide_ass(FOUR, cursor=0, ui=_ui(), artwork=none) == guide_ass(
        FOUR, cursor=0, ui=_ui()
    )


def test_omitting_artwork_altogether_is_the_same_as_none_of_it():
    assert guide_ass(FOUR, cursor=0, ui=_ui(), artwork=None) == guide_ass(
        FOUR, cursor=0, ui=_ui()
    )


def test_the_channel_number_gets_a_plate_so_it_cannot_be_lost_in_the_picture():
    # A green numeral on a bright cartoon frame is unreadable, and glow alone
    # does not fix it. The plate is opaque, so contrast stops depending on
    # whatever the picture happens to contain.
    arty = guide_ass(FOUR, cursor=0, ui=_ui(), artwork=FOUR_WITH_ART)
    plates = [p for p in arty.split("\n") if r"\c&H00000000" in p and r"\p1" in p]
    # One scrim for the whole guide, plus one plate for the one arty tile.
    assert len(plates) == 2


def test_a_plain_tile_gets_no_plate():
    plain = guide_ass(FOUR, cursor=0, ui=_ui())
    plates = [p for p in plain.split("\n") if r"\c&H00000000" in p and r"\p1" in p]
    assert len(plates) == 1  # the scrim only


def test_the_plate_sits_inside_the_picture_area():
    arty = guide_ass(FOUR, cursor=0, ui=_ui(), artwork=FOUR_WITH_ART)
    tile = page_tiles(len(FOUR), cursor=0)[0]
    plate = [p for p in arty.split("\n") if r"\c&H00000000" in p and r"\p1" in p][1]
    (px, py), = _positions(plate)
    assert tile.x <= px <= tile.x + tile.w
    assert tile.y <= py <= tile.y + art_rect(tile)[3]


def test_on_now_stays_in_the_band_with_the_name():
    arty = guide_ass(FOUR, cursor=0, ui=_ui(), on_now=0, artwork=FOUR_WITH_ART)
    tile = page_tiles(len(FOUR), cursor=0)[0]
    on_now_y = [y for line in arty.split("\n") if "ON NOW" in line
                for _, y in _positions(line)][0]
    assert on_now_y > tile.y + art_rect(tile)[3]
```

Add this helper beside `_positions` in the same file:

```python
def _name_y(ass, name):
    """The y of the line that draws ``name``."""
    for line in ass.split("\n"):
        if line.endswith(name):
            return _positions(line)[0][1]
    raise AssertionError(f"{name!r} was not drawn")
```

- [x] **Step 2: Run them and watch them fail**

Run: `.venv/bin/python -m pytest tests/test_guide.py -k "picture or plate or band" -v`
Expected: FAIL, `TypeError: guide_ass() got an unexpected keyword argument 'artwork'`

- [x] **Step 3: Add the parameter and the two layouts**

In `guide_ass`, add to the keyword-only arguments:

```python
    artwork: Optional[Sequence[bool]] = None,
```

and document it in the docstring:

```
    ``artwork`` is one flag per channel, True where a picture will be drawn
    behind that tile. This function draws no pictures - it only moves the text
    out of their way. A tile whose flag is False draws exactly as it always
    has, which is what lets pictures be added one show at a time.
```

Inside the tile loop, replace the three unconditional `parts.append(...)` text
lines with a branch:

```python
        has_art = bool(artwork) and rect.index < len(artwork) and artwork[rect.index]
        if has_art:
            art_x, art_y, art_w, art_h = art_rect(rect)
            band_y = art_y + art_h
            band_h = tile_h - art_h
            plate_size = max(18, int(art_h * 0.16))
            parts.append(
                _number_plate(
                    art_x + 8, art_y + 8, plate_size, number, green, ui, alpha=alpha
                )
            )
            parts.append(
                rf"{{\an5\pos({round(cx)},{round(band_y + band_h * 0.40)})"
                rf"{_style(ui, size=name_size, alpha=alpha)}}}{_escape(name)}"
            )
            if on_now is not None and rect.index == on_now:
                parts.append(
                    rf"{{\an5\pos({round(cx)},{round(band_y + band_h * 0.80)})"
                    rf"{_style(ui, size=tag_size, alpha=alpha)}}}ON NOW"
                )
        else:
            parts.append(
                rf"{{\an5\pos({round(cx)},{round(y + tile_h * 0.34)})"
                rf"{_style(ui, size=num_size, alpha=alpha)}}}{number:02d}"
            )
            parts.append(
                rf"{{\an5\pos({round(cx)},{round(y + tile_h * 0.66)})"
                rf"{_style(ui, size=name_size, alpha=alpha)}}}{_escape(name)}"
            )
            if on_now is not None and rect.index == on_now:
                parts.append(
                    rf"{{\an5\pos({round(cx)},{round(y + tile_h * 0.90)})"
                    rf"{_style(ui, size=tag_size, alpha=alpha)}}}ON NOW"
                )
```

The `_tile_frame` call stays where it is, before this branch, unchanged.

- [x] **Step 4: Add the plate**

In `nostalgiabox/guide.py`, beside `_tile_frame`:

```python
def _number_plate(
    x: float, y: float, size: int, number: int, color: str, ui: UiConfig,
    *, alpha: int,
) -> str:
    """The channel number on a solid dark block, over the picture.

    A green numeral on a bright cartoon frame is unreadable, and the OSD's
    usual defence - a dark outline and a phosphor glow - only helps. The plate
    guarantees it: whatever the artwork contains, the number is on black.

    Printed TV guides solve it the same way, which is a reasonable thing for a
    box pretending to be a television to copy.
    """
    plate_w = round(size * 2.1)
    plate_h = round(size * 1.35)
    plate = _filled_rect(
        x=x, y=y, w=plate_w, h=plate_h, fill="&H00000000",
        alpha=min(255, alpha + 30),
    )
    numeral = (
        rf"{{\an5\pos({round(x + plate_w / 2)},{round(y + plate_h / 2)})"
        rf"{_style(ui, size=size, alpha=alpha)}}}{number:02d}"
    )
    return plate + "\n" + numeral
```

- [x] **Step 5: Run them and watch them pass**

Run: `.venv/bin/python -m pytest tests/test_guide.py -v`
Expected: PASS

- [x] **Step 6: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS, 421 tests

- [x] **Step 7: Commit**

```bash
git add nostalgiabox/guide.py tests/test_guide.py
git commit -m "Lay a tile out around a picture, with the number on a plate"
```

---

### Task 5: Teach the player to draw a picture ✅ DONE (`f751b94`)

**Files:**
- Modify: `nostalgiabox/player.py` (`Player`, `MpvPlayer`, `MockPlayer`)
- Test: `tests/test_player_images.py` (create)

**Interfaces:**
- Consumes: `crop_box` from Task 2.
- Produces: `Player.show_image(slot: int, path: Path, x: int, y: int, w: int, h: int) -> None` and `Player.clear_images() -> None`. `MockPlayer.images: dict[int, tuple[Path, int, int, int, int]]` records calls for tests.

**Note:** these are concrete methods on `Player` with no-op defaults, NOT
abstract ones. Making them abstract would break every existing Player.

- [x] **Step 1: Write the failing tests**

Create `tests/test_player_images.py`:

```python
"""The player's picture layer, as far as it can be checked off a Raspberry Pi.

What the pictures LOOK like needs a television. What can be checked anywhere is
that the right file is asked for, at the right place, and that the layer is
emptied when the guide closes.
"""

from pathlib import Path

from nostalgiabox.player import MockPlayer, Player


def test_a_player_that_cannot_draw_pictures_ignores_them_quietly():
    # show_image is concrete with a no-op default, so a Player implementation
    # that predates the picture layer keeps working rather than failing to
    # instantiate.
    class Old(Player):
        def play(self, path, *, start=0.0): ...
        def play_loop(self, path): ...
        def stop(self): ...
        def set_volume(self, volume): ...
        def set_mute(self, muted): ...
        def get_time_pos(self): return None
        def show_text(self, text, duration): ...
        def set_overlay(self, overlay_id, ass, res_x, res_y): ...
        def clear_overlay(self, overlay_id): ...
        def close(self): ...

    Old().show_image(0, Path("tile.jpg"), 0, 0, 264, 198)
    Old().clear_images()


def test_the_mock_records_where_a_picture_was_put():
    player = MockPlayer()
    player.show_image(3, Path("/media/Rugrats/tile.jpg"), 76, 43, 264, 198)
    assert player.images[3] == (Path("/media/Rugrats/tile.jpg"), 76, 43, 264, 198)


def test_clearing_empties_the_whole_picture_layer():
    player = MockPlayer()
    player.show_image(0, Path("a.jpg"), 0, 0, 10, 10)
    player.show_image(1, Path("b.jpg"), 0, 0, 10, 10)
    player.clear_images()
    assert player.images == {}


def test_drawing_over_a_slot_replaces_what_was_there():
    player = MockPlayer()
    player.show_image(0, Path("a.jpg"), 0, 0, 10, 10)
    player.show_image(0, Path("b.jpg"), 5, 5, 20, 20)
    assert player.images == {0: (Path("b.jpg"), 5, 5, 20, 20)}
```

- [x] **Step 2: Run them and watch them fail**

Run: `.venv/bin/python -m pytest tests/test_player_images.py -v`
Expected: FAIL, `AttributeError: 'MockPlayer' object has no attribute 'show_image'`

- [x] **Step 3: Add the default methods to `Player`**

In `nostalgiabox/player.py`, inside `class Player`, after `clear_overlay`:

```python
    def show_image(
        self, slot: int, path: Path, x: int, y: int, w: int, h: int
    ) -> None:
        """Draw the picture at ``path`` scaled into ``w`` x ``h`` at ``x, y``.

        A second overlay layer, underneath the ASS one: the guide's tile
        pictures. Concrete rather than abstract, and a no-op by default, so a
        player that cannot draw pictures simply does not - the guide falls back
        to text, which it has to handle anyway for shows with no artwork.
        """

    def clear_images(self) -> None:
        """Remove every picture drawn by :meth:`show_image`."""
```

- [x] **Step 4: Implement it on `MockPlayer`**

In `MockPlayer.__init__`, beside `self.overlays`:

```python
        self.images: dict[int, Tuple[Path, int, int, int, int]] = {}
```

and as methods:

```python
    def show_image(self, slot: int, path: Path, x: int, y: int, w: int, h: int) -> None:
        self.images[slot] = (path, x, y, w, h)
        self._log(f"IMAGE {slot} {path.name} {w}x{h}+{x}+{y}")

    def clear_images(self) -> None:
        self.images.clear()
        self._log("CLEAR IMAGES")
```

- [x] **Step 5: Run them and watch them pass**

Run: `.venv/bin/python -m pytest tests/test_player_images.py -v`
Expected: PASS, 4 tests

- [x] **Step 6: Implement it on `MpvPlayer`**

Pillow is imported inside the method, not at module scope: it is a Pi
dependency and this module is imported by every test on a laptop without it.

In `MpvPlayer.__init__`, beside the other state:

```python
        # Tile pictures for the guide, keyed by slot. Kept so a redraw can
        # replace one and closing can remove them all.
        self._image_overlays: dict = {}
```

and as methods:

```python
    def show_image(self, slot: int, path: Path, x: int, y: int, w: int, h: int) -> None:
        try:
            from PIL import Image  # Pi-only dependency; see requirements.txt
        except ImportError:
            log.debug("Pillow is not installed, so tile pictures are skipped")
            return
        try:
            with Image.open(path) as src:
                cropped = src.convert("RGBA").crop(
                    crop_box(src.width, src.height, w, h)
                )
                scaled = cropped.resize((w, h), Image.LANCZOS)
        except OSError:
            # A corrupt or half-copied file must not take the guide down; the
            # tile simply keeps its text.
            log.warning("could not read tile picture %s", path, exc_info=True)
            return
        overlay = self._image_overlays.get(slot)
        if overlay is None:
            overlay = self._mpv.create_image_overlay()
            self._image_overlays[slot] = overlay
        overlay.update(scaled, pos=(x, y))

    def clear_images(self) -> None:
        for overlay in self._image_overlays.values():
            try:
                overlay.remove()
            except Exception:  # pragma: no cover - libmpv specific
                log.debug("removing an image overlay failed", exc_info=True)
        self._image_overlays.clear()
```

Add `from .artwork import crop_box` to the imports at the top of `player.py`.

- [x] **Step 7: Add Pillow to the Pi extras**

In `requirements.txt`, under the Pi runtime section:

```
# Pillow>=10.0.0     # scales show artwork for the guide's tile pictures
```

In `pyproject.toml`, in the `pi` extras list beside `python-mpv`:

```
    "Pillow>=10.0.0",
```

- [x] **Step 8: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS, 425 tests. Pillow is NOT installed locally; if any test fails
with `ModuleNotFoundError: PIL`, the import is at module scope and must move
inside the method.

- [x] **Step 9: Commit**

```bash
git add nostalgiabox/player.py tests/test_player_images.py requirements.txt pyproject.toml
git commit -m "Give the player a layer for pictures"
```

---

### Task 6: Put the two layers together ✅ DONE (`e3ef3fe`)

**Files:**
- Modify: `nostalgiabox/app.py` (`_draw_guide`, `_close_guide`)
- Test: `tests/test_app.py`

**Interfaces:**
- Consumes: `Channel.peek_next` (Task 1), `tile_image_for` (Task 2), `page_tiles` / `art_rect` (Task 3), `guide_ass(artwork=...)` (Task 4), `Player.show_image` / `clear_images` (Task 5).
- Produces: nothing further.

- [x] **Step 1: Write the failing tests**

⚠️ **`build_app` cannot be used as-is here.** Its `make_show` helper drops
episodes LOOSE in the channel folder (`tmp_path/dragon/dragon_ep01.mp4`), so
`show_name_for` finds no show, `tile_image_for` returns None, and every artwork
test would pass while proving nothing. A real channel is
`<channel>/<show>/<episode>`. Build that.

In `tests/test_app.py`, in the guide section:

```python
# -- tile pictures ----------------------------------------------------------


def build_arty_app(tmp_path):
    """An app whose channel 3 holds a show WITH a picture.

    Channel 2 keeps build_app's loose episodes (no show, so no picture) and is
    where the box starts. The artwork is on channel 3, which is deliberately
    NOT the channel on air: only the channel on air has anything playing, so a
    picture on any other tile can only have come from peek_next.
    """
    show = tmp_path / "nickjr" / "Rugrats"
    show.mkdir(parents=True)
    for i in range(1, 4):
        (show / f"ep{i:02d}.mp4").write_bytes(b"\x00")
    art = show / "tile.jpg"
    art.write_bytes(b"not really a jpeg - the box only needs the path")

    app, player, clock = build_app(
        tmp_path,
        channels=[
            {"number": 2, "name": "Dragon Tales", "path": str(tmp_path / "dragon")},
            {"number": 3, "name": "Nick Jr", "path": str(tmp_path / "nickjr")},
        ],
    )
    return app, player, art


def test_a_show_with_a_picture_gets_one_drawn_on_its_tile(tmp_path):
    app, player, art = build_arty_app(tmp_path)
    app.start()
    send(app, Action.HOME)
    assert art in [entry[0] for entry in player.images.values()]


def test_a_channel_you_are_not_watching_still_gets_a_picture(tmp_path):
    # The picture is on channel 3; the box is on channel 2. Nothing is playing
    # on channel 3, so this can only have come from asking it what it WOULD
    # play - which is the whole point of peek_next.
    app, player, art = build_arty_app(tmp_path)
    app.start()
    assert app.lineup.current.number == 2
    send(app, Action.HOME)
    assert art in [entry[0] for entry in player.images.values()]


def test_a_show_with_no_picture_gets_no_picture(tmp_path):
    app, player, _ = build_arty_app(tmp_path)
    app.start()
    send(app, Action.HOME)
    # Channel 2's episodes sit loose with no show folder, so there is nothing
    # to find. One picture drawn, not two.
    assert len(player.images) == 1


def test_a_box_with_no_artwork_at_all_draws_no_pictures(tmp_path):
    app, player, _ = build_app(tmp_path)
    app.start()
    send(app, Action.HOME)
    assert player.images == {}


def test_the_picture_sits_in_the_top_of_its_own_tile(tmp_path):
    app, player, art = build_arty_app(tmp_path)
    app.start()
    send(app, Action.HOME)
    index = app.lineup.index_of(3)
    rect = [r for r in page_tiles(len(app.lineup), app.guide.cursor)
            if r.index == index][0]
    _, x, y, w, h = [e for e in player.images.values() if e[0] == art][0]
    art_x, art_y, art_w, art_h = art_rect(rect)
    assert (x, y) == (round(art_x), round(art_y))
    assert (w, h) == (round(art_w), round(art_h))


def test_closing_the_guide_takes_the_pictures_away(tmp_path):
    app, player, _ = build_arty_app(tmp_path)
    app.start()
    send(app, Action.HOME)
    assert player.images
    send(app, Action.LAST_CHANNEL)  # Back
    assert player.images == {}


def test_the_guide_timing_out_takes_the_pictures_away(tmp_path):
    # Otherwise they would sit over the programme with nothing left to remove
    # them.
    show = tmp_path / "nickjr" / "Rugrats"
    show.mkdir(parents=True)
    (show / "ep01.mp4").write_bytes(b"\x00")
    (show / "tile.jpg").write_bytes(b"picture")
    app, player, clock = build_app(
        tmp_path, guide={"timeout_seconds": 20},
        channels=[{"number": 3, "name": "Nick Jr", "path": str(tmp_path / "nickjr")}],
        start_channel=3,
    )
    app.start()
    send(app, Action.HOME)
    clock.advance(21)
    app.tick()
    assert player.images == {}
```

Import `page_tiles` and `art_rect` from `nostalgiabox.guide` at the top of
`tests/test_app.py`. Check how `FakeClock` is advanced and how `app.tick()` is
called in the existing `test_the_guide_closes_itself_after_the_timeout`, and
match it exactly — the last test above is that one with pictures added.

**On the cache:** `artwork._first_existing` is `lru_cache`d by directory. Every
test uses its own `tmp_path`, so no test can see another's answer. But a test
that creates `tile.jpg` AFTER the guide has already drawn once would get the
cached `None`. Create artwork before `app.start()`, as above.

- [x] **Step 2: Run them and watch them fail**

Run: `.venv/bin/python -m pytest tests/test_app.py -k picture -v`
Expected: FAIL. `player.images` stays empty because nothing in the app draws
pictures yet, so the assertions on it fail. (It exists as an attribute already,
from Task 5.)

- [x] **Step 3: Resolve artwork and draw both layers**

In `nostalgiabox/app.py`, replace `_draw_guide` with:

```python
    def _draw_guide(self) -> None:
        """Draw both layers of the guide: the pictures, then the text on top."""
        channels = list(self.lineup)
        artwork = [self._tile_picture(channel) for channel in channels]
        self._draw_guide_pictures(artwork)
        self.overlay.show_guide(
            guide_ass(
                [(c.number, c.name) for c in channels],
                self.guide.cursor,
                self.config.ui,
                on_now=self.lineup.index_of(self.lineup.current.number),
                dim=self.config.guide.dim,
                page_cols=self.config.guide.page_cols,
                page_rows=self.config.guide.page_rows,
                artwork=[picture is not None for picture in artwork],
            )
        )

    def _tile_picture(self, channel: Channel) -> Optional[Path]:
        """The picture for whatever ``channel`` would play, or None.

        For the channel on air that is what is playing; for every other channel
        it is what tuning there would start. Either way the tile promises the
        programme you would actually get.
        """
        if channel.number == self.lineup.current.number and self._playing_path:
            episode = self._playing_path
        else:
            episode = channel.peek_next()
        if episode is None:
            return None
        return tile_image_for(episode, channel.config.path)

    def _draw_guide_pictures(self, artwork: Sequence[Optional[Path]]) -> None:
        """Put a picture in the top of every visible tile that has one."""
        self.player.clear_images()
        rects = page_tiles(
            len(artwork),
            self.guide.cursor,
            self.config.guide.page_cols,
            self.config.guide.page_rows,
        )
        for slot, rect in enumerate(rects):
            picture = artwork[rect.index]
            if picture is None:
                continue
            art_x, art_y, art_w, art_h = art_rect(rect)
            self.player.show_image(
                slot, picture, round(art_x), round(art_y), round(art_w), round(art_h)
            )
```

Add to the imports at the top of `app.py`:

```python
from .artwork import tile_image_for
from .guide import Guide, art_rect, guide_ass, page_tiles
```

(replacing the existing `from .guide import Guide, guide_ass`), and add
`Sequence` to the `typing` import.

- [x] **Step 4: Take the pictures away when the guide closes**

In `_close_guide`, after `self.overlay.clear_guide()`:

```python
        self.player.clear_images()
```

And in `_tick_guide`, inside the `if not self.guide.is_open:` branch that
follows `self.guide.tick()`, beside `self.overlay.clear_guide()`:

```python
            self.player.clear_images()
```

Without this the pictures would stay on screen after the guide timed out,
sitting over the programme with no way to remove them.

- [x] **Step 5: Run them and watch them pass**

Run: `.venv/bin/python -m pytest tests/test_app.py -v`
Expected: PASS

- [x] **Step 6: Run the whole suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS, 430 tests

- [x] **Step 7: Commit**

```bash
git add nostalgiabox/app.py tests/test_app.py
git commit -m "Draw the pictures under the guide, and take them away with it"
```

---

### Task 7: Write down what only a television can answer ✅ DONE

**Files:**
- Modify: `docs/superpowers/specs/2026-08-20-guide-artwork-design.md`
- Modify: `README.md`

- [x] **Step 1: Record the decisions taken during the build**

In the spec, change the status line to:

```markdown
**Status:** Built (date it the day it lands). Not yet seen on a television.
```

and replace the **Open** section's resolved entries: artwork that is not 4:3 is
**cropped to fill, centred** (`artwork.crop_box`); scaling uses **Pillow**,
imported lazily inside `MpvPlayer`; a page mixing tiles with and without
pictures uses **per-tile fallback**.

- [x] **Step 2: Add the artwork convention to the README**

In `README.md`, in the section describing how to lay out the USB drive, add:

```markdown
### Giving a show a picture

Put a **`tile.jpg`** in the show's own folder, beside its seasons:

```
Nick Jr/                 <- the channel
└─ Rugrats/              <- the show
   ├─ tile.jpg           <- the picture
   ├─ Season 01/
   └─ Season 02/
```

It shows up on that show's tile in the channel guide. **Supply 4:3 images,
1024x768** — the tile's picture area is 264x198, which is exactly 4:3, the same
shape as the programmes. Anything else is cropped to fill, centred. `tile.png`
works too.

A show with no picture keeps the old tile: a big channel number and the show's
name. So pictures can be added one show at a time.
```

- [x] **Step 3: List what still needs the Pi**

Add to the spec's Open section:

```markdown
- **Z-order has never been checked.** The pictures are a separate mpv overlay
  layer from the ASS text. Nothing guarantees the text lands on top of them
  rather than behind. If the tile frames or names vanish behind the pictures,
  this is why.
- **The band may be too tight.** 43px of name and 31px of ON NOW inside 90px
  is arithmetic, not observation.
- **Pillow must be installed on the Pi**: `pip install Pillow`. Without it the
  box quietly draws no pictures - by design, but worth knowing when the first
  tile.jpg appears to do nothing.
```

- [x] **Step 4: Commit**

```bash
git add docs/superpowers/specs/2026-08-20-guide-artwork-design.md README.md
git commit -m "Write down the artwork convention, and what only a TV can answer"
```

---

## After the plan

Nothing here has been seen on a television. Before calling it done, on the Pi:

1. `pip install Pillow` in the box's environment.
2. Drop one `tile.jpg` into one show folder and open the guide.
3. Check the picture appears, that the frame and the name are drawn ON TOP of
   it, and that the number on its plate is readable against the artwork.
4. Check a page with one picture and seven plain tiles does not read as broken.
