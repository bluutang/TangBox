# Show artwork on the guide tiles — design

**Date:** 2026-08-20
**Status:** **Built 2026-08-20**, on branch `guide-artwork`. Not yet seen on a television.
**Companion:** `2026-08-17-channel-guide-design.md` (Phase 1, built),
`2026-08-20-channel-numbering-design.md` (paging, built the same day).

---

## Why this exists

The guide's tiles carry a channel number and a show name. Neither child can
read, so a tile currently tells them nothing. This is the "Phase 2" that has
been parked since the guide was first designed, and it is the part that matters
most: a picture is the only thing on that screen a 2-year-old can use.

---

## Decided

### A tile shows a picture of the show, not the channel

Brian's call. One picture per show, not per channel — so the tile changes as the
channel's programming changes, rather than being a station logo.

### The picture is what you will get if you tune there

Brian's call, chosen over a real broadcast clock.

For the channel playing, the tile shows what is playing. For every other
channel, it shows what that channel would start if OK were pressed now.

**The alternative, and why it lost.** `channel.py` already contains
`BroadcastSchedule`, which can answer "what would be airing on this channel
right now" for any moment on the clock — every channel running continuously
whether or not anyone is watching, like real cable. It is not in use: the box
runs `tune_in: random` with one channel on `resume`, so nothing is happening on
channel 21 while channel 11 is on.

Turning it on would cost two things. It changes how tuning in feels, replacing
the "walked into the room" illusion that is already shipped and liked. And it
needs the length of every episode, which means measuring the whole library and
remembering the answer, or accepting a boot that takes minutes instead of 21
seconds.

What-you-will-get is truthful, needs no clock, and is what-you-see-is-what-you-
get for a child choosing by picture. The shuffle bag already knows what it will
hand out next (`ShuffleBag._queue[-1]`); exposing it is close to a one-line
change.

### Artwork lives in the show's own folder

Brian's call, chosen over one central artwork folder.

```
USB drive
└─ Nick Jr/                  ← the channel (a folder of shows)
   ├─ Rugrats/               ← the show
   │  ├─ tile.jpg            ← the picture
   │  ├─ Season 01/
   │  └─ Season 02/
   └─ Blue's Clues/
      ├─ tile.jpg
      └─ Season 01/
```

It travels with the media: copy a show to a new drive and its picture goes too.
Nothing to configure, nothing to keep in sync, and no filename that has to match
a folder name elsewhere. `tile.png` is accepted as well, since artwork often
arrives that way.

This fits the layout the box already assumes. `show_name_for()` in `channel.py`
takes the FIRST path component under the channel root as the show, so
`<channel>/<show>/` is established, not new.

### The text goes below the picture

Brian's call. The picture is the top of the tile; the show name sits under it.

### Everything except the channel number stays off the picture

The number has to sit on the picture, because the picture takes the space the
number used to have. Brian's requirement: **it must contrast with whatever is
behind it.**

The OSD's usual defence is a dark outline plus phosphor glow, which helps but
guarantees nothing — a bright cartoon frame can still swallow a green numeral.
So the number gets a **solid dark plate** behind it, the way a printed TV guide
prints its number on a block. Contrast then does not depend on the picture at
all.

The show name and `ON NOW` need no such treatment: they are in the band below
the picture, over the same dimmed video the guide's text already sits on.

---

## The tile, measured

The tile is **264 x 288** canvas pixels (396 x 432 on a 1080p television; the
canvas is 1280x720 and mpv scales it).

| Part | Size | Notes |
|---|---|---|
| Picture | 264 x 198 | exactly 4:3 — the shape the programmes already are |
| Text band | 264 x 90 | show name at 43px, `ON NOW` at 31px beneath it |
| Number plate | on the picture | top-left, dark plate, green numeral |

**Artwork to supply: 4:3, 1024x768.**

The picture area is 264x198 on the canvas, so what a screen actually uses is
264x198 at 720p, **396x297 at 1080p** (Brian's television) and 792x594 at 4K.
792x594 is therefore the most any screen can use; 1024x768 covers it with room
to spare and is a size artwork can actually be found in.

Bigger is actively worse: `MpvPlayer.show_image` decodes and LANCZOS-resizes
every picture each time the guide opens or turns a page, so a 4000px image is
decoded in full and then thrown away down to 396px. 800-1500px wide is the
range. Anything not 4:3 is cropped to fill, centred.

The 90px band is arithmetic, not observation: 43 + 31 = 74, leaving 16px of air
across two lines. It may prove tight on a television.

---

## A show with no picture

The tile falls back to exactly what it draws today: the large channel number,
the show name centred, `ON NOW` beneath.

This is what makes the feature safe to build before any artwork exists. The box
looks untouched until the first `tile.jpg` appears, and pictures can be added
one show at a time rather than all fifty before anything works. Brian has 50
shows and no artwork today, so every tile takes this path on day one.

A page mixing tiles with and without pictures must look deliberate rather than
broken. Not yet resolved — see Open.

---

## How it is drawn

libass draws text and shapes, not photographs, so the existing overlay cannot
carry a picture. mpv can lay bitmaps over the video as a **separate layer**, and
python-mpv exposes it (`create_image_overlay`, `overlay_add`) — verified present
in the installed binding, not assumed.

Two layers rather than one is worth having on its own merits: moving the cursor
redraws only the cheap text layer, so browsing stays as quick as it is now, and
only turning a page swaps pictures.

Pictures must be scaled to tile size before mpv will take them. Two routes:

- **Pillow** (recommended). python-mpv's image overlay works with it directly.
  One new package on the Pi. Seventeen tiles at 264x198 BGRA is about 3.5MB of
  memory, which is nothing on a 4GB Pi.
- **Pre-scale with ffmpeg into a raw cache.** Adds no dependency, since ffmpeg
  is already required, and makes drawing instant. But it adds a cache that has
  to be invalidated when artwork changes.

Recommended: Pillow, for the much simpler code. Not yet accepted.

---

## What cannot be checked on a Mac

Which picture is chosen, where it is positioned, and what happens when it is
missing are all testable here. **Whether it actually appears on the television
is not.** simulate.py's docstring explains why: libmpv driven from Python cannot
open a window on macOS.

An approximation can be rendered for a look at the design, but that is an image
composed by hand, not proof the runtime path works. This one needs the Pi.

---

## Resolved during the build

- **Artwork that is not 4:3 is cropped to fill**, centred (`artwork.crop_box`).
  Letterbox bars inside a tile this small waste the only space a child can use.
- **Scaling uses Pillow**, imported lazily inside `MpvPlayer` so the tests still
  run on a Mac without it. It is in the `pi` extras.
- **A mixed page uses per-tile fallback.** Checked by rendering one: three tiles
  with pictures beside five without does not read as broken. It does put the
  show names at two different heights across the page, because a plain tile
  centres its name while a picture tile drops it into the band. Judge that on
  the television.
- **The picture is FITTED, not derived from the tile's width.** The first
  attempt took its height from the width, which is right on a 264x288 tile and
  wrong on the 552x305 tiles a one-page lineup produces - a 4:3 picture as wide
  as that is 414 tall and bursts out of the bottom. `art_rect` now reserves the
  band as a proportion of the tile and fits the largest 4:3 picture above it.

## Open

- **Whether 90px of band is enough** for two lines on a television.
- **The `ON NOW` marker** may want to move onto the picture, once there is a
  picture to judge it against. It would then need the same dark plate as the
  number.
- **Where the pictures come from.** Fifty shows is fifty images to find, crop
  and name. Not a code problem, but it is the thing standing between this and a
  tile a child can use.

## Only a television can answer these

- **Z-order has never been checked.** The pictures are a separate mpv overlay
  layer from the ASS text. Nothing in the code guarantees the text lands on top
  of them. If the tile frames or the show names vanish behind the pictures,
  this is why.
- **Pillow must be installed on the Pi.** Without it the box quietly draws no
  pictures - by design, but worth knowing when the first `tile.jpg` appears to
  do nothing.
- **Whether the number's plate is dark enough** against real artwork rather
  than the colour bars it was rendered over.

## Not in this design

- The broadcast clock. Considered and rejected above; `BroadcastSchedule` stays
  unused.
- Channel numbering. Waiting on the catalogue — Brian, 2026-08-20.
- Age-gating. Explicitly set aside — Brian, 2026-08-20.
