# Channel guide (the "home screen") — design

**Date:** 2026-08-17
**Status:** Design agreed. Not implemented.
**Next step:** implementation plan, then code (test-first).

---

## Why

TangBox has no user interface. It plays video full screen and listens for
channel up/down and direct number entry. That is deliberate and it works, but it
has a ceiling: you have to already know what is on channel 6.

Two things push against that ceiling.

**Movie channels are categorised by franchise and genre**, so instead of one
"Movies" channel there will be several — Disney, Pixar, Ghibli, and so on. That
takes the lineup past nine channels.

**Past nine channels, direct tuning gets worse.** Single-digit channels tune
instantly. Double digits make the box pause to see whether a second digit is
coming. So exactly when the lineup grows enough to be hard to remember, the
fastest way to navigate it also slows down.

A visual guide answers both. It is not a replacement for number entry — a child
who knows Arthur is 4 should never need it. It is what you use when you do not
know, or when you want to browse.

---

## Scope

Three phases. Only phase 1 is specified in full here.

| Phase | Contains | When |
|---|---|---|
| **1** | The guide itself, plus a random-channel button | First |
| **2** | `tile.jpg` artwork on the tiles | After the Pi runs |
| **3** | CRT intensity cycle, bedtime sign-off | Later, on a working box |

Phase 2 is deliberately after the box exists, because it depends on something
that cannot be verified on a Mac. See "The one unknown" below.

---

## Phase 1 — the guide

### What it does

Press **Home** and a grid of channels appears over the picture. The picture keeps
playing underneath, dimmed. Move with the d-pad, press **OK** to tune, press
**Back** to leave without changing anything.

### What it looks like

```
   ┌────────┐  ┌────────┐  ┌────────┐
   │   02   │  │   04   │  │   06   │
   │ DRAGON │  │ ARTHUR │  │ MAGIC  │
   │ TALES  │  │        │  │ SCHOOL │
   └────────┘  ╚════════╝  └────────┘
                 ▲ ON NOW

   ┌────────┐  ┌────────┐
   │   08   │  │   10   │
   │ ROGERS │  │ DISNEY │
   └────────┘  └────────┘
```

Same phosphor green, same VT323 font, same glow as the existing channel banner.
It should read as part of the television, not as an app that landed on one.

The cursor starts on whatever is currently playing, and that channel is marked
`ON NOW`. So Home then OK always means "never mind".

### Grid sizing

The channel count is not known and will grow. The grid computes itself:

```
cols = min(5, ceil(sqrt(n)))
rows = ceil(n / cols)
```

Four channels give 2×2. Nine give 3×3. Twelve give 4×3. The cap of five columns
exists because text has to be readable from a sofa, not a desk.

No paging. If the lineup ever passes about twenty channels the grid stops being
readable and the answer is a scrolling list, which is a different design. Build
that if it ever happens, not before.

### Input

The remote is a GE Big Button Universal (83036), chosen because it has a d-pad,
a full number pad, Home and Back, and spare buttons. It reaches the Pi through a
Flirc adapter, which learns any infrared remote and reports it as a USB keyboard.
Because Flirc lets any button send any keystroke, the printing on the buttons is
irrelevant. We choose the mapping.

**The d-pad gets its own actions.** Today `keymap.py` maps `KEY_UP` and
`KEY_CHANNELUP` to the same `CHANNEL_UP` action, so the d-pad and the dedicated
channel buttons are indistinguishable. Splitting them is what lets volume and
channel keep working while the guide is open.

New actions: `NAV_UP`, `NAV_DOWN`, `NAV_LEFT`, `NAV_RIGHT`, `HOME`, `RANDOM`.

| Key | Action | Guide closed | Guide open |
|---|---|---|---|
| `KEY_UP` / `KEY_DOWN` | `NAV_UP` / `NAV_DOWN` | Change channel | Move cursor |
| `KEY_LEFT` / `KEY_RIGHT` | `NAV_LEFT` / `NAV_RIGHT` | Volume down / up | Move cursor |
| `KEY_CHANNELUP` / `KEY_CHANNELDOWN` | `CHANNEL_UP` / `CHANNEL_DOWN` | Change channel | Change channel |
| `KEY_VOLUMEUP` / `KEY_VOLUMEDOWN` | `VOLUME_UP` / `VOLUME_DOWN` | Volume | Volume |
| `KEY_HOME` / `KEY_HOMEPAGE` | `HOME` | Open the guide | Close it |
| `KEY_INFO` | `INFO` | Re-show the channel banner | — |
| `KEY_BACK` | `LAST_CHANNEL` | Previous channel | Close, no change |
| `KEY_ENTER` / `KEY_OK` | `ENTER` | Open the guide | Tune to the cursor |
| `KEY_KPDOT` | `RANDOM` | Random channel | — |
| `0`–`9` | `DIGIT` | Tune directly | — |

Two deliberate redundancies:

**`OK` opens the guide as well as Home.** Single digits tune instantly, so `OK`
does almost nothing while watching. Making it open the guide means the box still
works on a remote with no Home button at all.

**Channel and volume also move the cursor while the guide is open**, as a
fallback. A remote with no d-pad still has four directions. This costs a couple
of lines and keeps the box usable with whatever remote is in the drawer.

### The three behavioural calls

**Selecting the channel you are already watching closes the guide without
re-tuning.** `tune_in` is `random`, so re-tuning would restart the channel on a
different episode. Pressing OK on what you are already watching must never
interrupt it.

**The guide closes itself after 20 seconds with no input.** A child who wanders
off should not leave the television dimmed under a menu all evening.

**Power still works while the guide is open.** It closes the guide and goes to
standby rather than being swallowed.

### Dimming

A full-canvas half-transparent black rectangle drawn behind the tiles, using the
same rectangle helper the volume bar already uses (`_filled_rect` in
`overlay.py`, with alpha). Start at 66%.

No player changes and nothing to restore. It disappears with the rest of the
overlay.

### Drawing

Everything goes through the existing overlay system: ASS events on the fixed
1280×720 virtual canvas, which mpv scales to the television. `overlay.py` already
draws text, filled rectangles and circles this way.

The whole guide — scrim, tiles, cursor, labels — is one ASS string in **one new
overlay slot** (`_ID_GUIDE = 5`; ids 1–4 are taken by the channel banner, volume,
standby and messages). One slot means one draw call and one clear.

**The guide spans the full 16:9 canvas**, unlike the channel banner and volume
bar, which are laid out inside the 4:3 picture area. This is intentional: the
banner sits over the picture, the guide replaces it.

### Files

| File | Change |
|---|---|
| `nostalgiabox/guide.py` | **New.** `guide_ass()` pure drawing function; `Guide` state class |
| `nostalgiabox/actions.py` | Six new `Action` members |
| `nostalgiabox/input/keymap.py` | Map the new keys; split d-pad from channel/volume |
| `nostalgiabox/app.py` | ~15 lines: offer each event to the guide first when open |
| `nostalgiabox/overlay.py` | One new slot id; alpha on `_filled_rect` |

Nothing is restructured. The guide is a layer that intercepts input when open and
is completely inert when closed.

The split of `guide.py` into a pure drawing function plus a small state class
follows the pattern `overlay.py` already uses — free functions that build ASS are
easy to test without a player.

### Random channel

The `•` button picks a channel at random, excluding the one currently playing,
and tunes to it using the same path as digit entry.

Excluding the current channel matters. Without it, the button sometimes appears
to do nothing, or restarts the current channel on a different episode, which
reads as a fault.

This belongs in phase 1 because it is about ten lines and reuses an existing
code path. For a pre-reader it is the most valuable button on the remote: it
always does something good and requires no reading.

### Testing

All of phase 1 is verifiable on a Mac with no Pi and no television.

- `guide_ass()` is a pure function. Tests assert on its output directly.
- Cursor movement, wrapping and the 20-second timeout are pure state.
- `player.py` already has a fake player that records overlays into a dictionary,
  which is how the existing overlay tests work.

Test-first throughout. The current suite is 111 tests; this should add
meaningfully to that before any of it is wired into `app.py`.

---

## Phase 2 — artwork

Each show folder may contain a **`tile.jpg`**. Where one exists the tile shows
it; where it does not, the tile falls back to the text design from phase 1.

The text tiles are therefore not thrown away. They are the fallback for a show
added last night that has no artwork yet, and for any image that fails to load.

### Why this matters more than it looks

**The users are 2 and 4 years old. Neither can read.** A 4-year-old may
recognise the digit `4`; a 2-year-old will not reliably read anything. So the
text tiles are close to useless to the people the box exists for.

Artwork is not polish here. It is what makes the guide navigable by its actual
users. Phase 2 stays after phase 1 only because the image path cannot be verified
without a Pi, not because it is less important.

The same reasoning promotes the `•` random-channel button. For a 2-year-old it
may be the only control they ever need: one button, no reading, no aiming.

### Tile appearance requirements

**Consistent size.** Every tile is identical regardless of what its source image
looks like. Artwork is normalised when prepared: scaled to fill the tile and
centre-cropped to the tile's aspect ratio. A grid of mismatched shapes reads as
broken, and inconsistent sizing makes the focused tile harder to pick out.

Collect **landscape** artwork, roughly **640×360**. Tiles are 16:9-ish, so a 2:3
portrait movie poster either crops through the middle or floats in bars. Banner
art or a good still, not a poster. The largest a tile ever renders is about
825×465 real pixels (2×2 grid on a 1080p screen).

**Rounded corners.** Applied when the image is prepared, by writing transparent
alpha into the corner pixels of the BGRA data. mpv's image overlay respects
alpha, so no runtime masking is needed and it costs nothing per frame.

**Focus is unmistakable.** Three things change at once on the focused tile, so it
reads from a sofa at ten feet:

1. A bright phosphor-green border, thicker than the resting state
2. A soft outer glow, matching the existing OSD's bloom
3. **Unfocused tiles dim.** The focused one stays at full brightness

The third is the one that does the work for a small child. A single bright thing
among dim ones needs no explanation; a subtly different border does.

**Why supplied artwork rather than generated frames.** Grabbing a frame from an
episode is a lottery: black fades, mid-blink faces, the wrong episode's title
card. It also needs an ffmpeg pass per channel and a cache keyed to files on a
drive that changes whenever the USB stick is unplugged. A `tile.jpg` either
exists or it does not, it is chosen rather than sampled, and adding one is the
same motion as adding the show.

### The one unknown

mpv draws images through a completely different mechanism than text. Text is an
ASS overlay on a virtual canvas; images are raw pixel data at **actual screen
coordinates**. The two have to be reconciled against the television's real
resolution.

Everything else in this project has been verifiable headless. This cannot be.
There is no video output at all on macOS, so whether images composite correctly
over video on the Pi's framebuffer can only be discovered on the Pi.

That is the entire reason phase 2 comes after the box runs. It is not a hard
problem, but it is one that needs hardware to answer, and it should be met with
everything else already working.

---

## Phase 3 — noted, not designed

### CRT intensity cycle

`INPUT` steps through **none → Soft Frame → Glass & Grain → heavy CRT** and back,
flashing the name in the existing green banner.

**It does not persist.** On restart the box returns to whatever `config.yaml`
says. A child cannot permanently change how the television looks, and the config
file stays the source of truth. A setting you fall in love with on the sofa gets
written into the file properly.

The value is real: the picture cannot be judged from a Mac, so being able to A/B
the look on the actual television while watching actual footage turns "SSH in,
edit four numbers, restart" into pressing a button.

### Bedtime sign-off

**Parked.** Brian wants to think about it further. Where the thinking got to:

- **Triggered by a button (`*`), not a schedule.** Dropping the clock removes a
  scheduler, a config block, and the weekday/weekend question entirely.
- **One rule instead of two.** On trigger, look at how much of the current thing
  is left. Under about half an hour, let it finish. More than that, warn for ten
  minutes and stop. An episode always falls one side of that line and a film the
  other, so nothing has to be labelled a show or a movie.
- **Persistent on-screen message** while the sign-off is pending.
  `overlay.py` already treats a duration of zero as "leave until cleared".
- **Cancellable with Back**, and the message says so: `PRESS BACK TO CANCEL`.
  This is a box with no manual, so a message that explains its own escape is
  worth more than documentation. Cancellable during the warning, committed once
  the goodnight sequence starts.
- **Then a clean power-off.** Colour bars, then the Pi halts properly.

**Getting it back on.** The Rastech supply has an inline switch, so cycling power
starts it again. The Pi 5 also has a physical power button on the board, which
wakes it from a halted state — whether that is reachable depends on the case.

Almost every piece already exists: the message banner, `static_gen.py` for the
bars, the shutdown path from `power_off_on_min_volume`, and a main loop that
already ticks every iteration.

---

## The remote, fully mapped

GE Big Button Universal 83036, via Flirc.

| Button | Watching | Guide open |
|---|---|---|
| D-pad ▲▼ | Change channel | Move cursor |
| D-pad ◀▶ | Volume | Move cursor |
| OK | Open the guide | Tune to the tile |
| 0–9 | Tune directly | — |
| 🏠 Home | Open the guide | Close it |
| ↰ Back | Previous channel | Close, no change |
| CH ▲▼ | Change channel | Change channel |
| VOL +/− | Volume | Volume |
| Mute | Mute | Mute |
| Power | Standby | Standby |
| `ch↩` | Previous channel | — |
| `≡` | Re-show the channel banner (info) | — |
| ENTER | Confirm a two-digit channel | — |
| `•` | Random channel | — |
| `INPUT` | CRT intensity cycle *(phase 3)* | — |
| `*` | Bedtime sign-off *(phase 3)* | — |

**`SETUP`, `TV` and `AUX` cannot be mapped.** They are mode selectors that tell
the remote which code set to transmit; they emit nothing themselves.

**Use the two-device feature.** Program `AUX` to a brand you do not own and teach
Flirc only those codes. Then `AUX` drives TangBox and `TV` drives the actual
television, from one remote, with no conflict.

**Try HDMI-CEC first.** `input.cec` is already true. If the television's own
remote drives the box acceptably, the Flirc and the GE are unnecessary.

---

## Non-goals

- **No picking a specific episode or film.** Tiles are channels. Drilling into a
  channel to choose a title needs a "play this exact file" path the player does
  not have, plus scrolling and a back stack, and it changes what the box is. The
  broadcast illusion is the point.
- **No colour filters** (sepia, invert). A button that leaves a child watching
  Arthur in inverted colours, unable to explain what they pressed, is a support
  burden on a box whose promise is that it behaves like a television.
- **No paging** until the lineup actually outgrows one screen.
- **No persistence** of the CRT cycle. The config file stays authoritative.

---

## Open questions

- **Is the tile text large enough at ten feet?** The mock-up was judged on a
  monitor at arm's length. Nine channels shrinks tiles noticeably, and the
  lineup is heading that way. May force an earlier column cap.
- **Is 66% dimming right?** It was judged against colour bars, about the
  brightest thing that could ever sit behind the guide. Real footage will read
  darker.

Both are answerable in ten seconds once the box is on a television, and both are
single numbers.
