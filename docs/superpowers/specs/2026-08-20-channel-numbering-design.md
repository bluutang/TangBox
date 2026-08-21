# Channel numbering and the scrollable guide — design

**Date:** 2026-08-20
**Status:** Structure decided. Numbering recommended but not chosen. **Guide paging
built 2026-08-20** - see "How the guide pages", below.
**Supersedes:** the four-channel lineup (`Los Pequeños` / `Caricaturas` / `Cine` / `En Inglés`)
in `config.pi.yaml`, which was designed before there was a library.
**Companion:** `2026-08-17-channel-guide-design.md` — Phase 1 of that guide is built.

---

## Why this exists

The old lineup had four channels grouped by age and language. It was designed
around shows Brian *wanted*, before he had any. He now has a real list — 50
series and 40 films — and the shape of it broke the old scheme:

- It spans **ages 1 to 10+**, from Teletubbies to Dragon Ball Z. A single flat
  lineup means a 2-year-old can reach anything.
- It is **mostly Spanish dubs of American shows**, so "En Inglés" as a channel
  stopped meaning much.
- It is big enough that four channels wastes it and twenty is plausible.

---

## The constraint everything else follows from

**A channel is a folder. A show lives in exactly one folder.**

So network, theme and age cannot all classify the same show at once. Rugrats is
Nickelodeon, a cartoon, and roughly 4+. It gets one home, not three. Changing
that would mean a fundamentally different design — a database rather than a
directory tree — and is not worth it.

---

## Decided

### Network is the primary axis

The folder a show lives in is its **network**: Nickelodeon, Cartoon Network,
Disney, Warner Bros, Anime, Apple TV+, Netflix, Prime Video, PBS/Preschool,
Televisa.

Brian's call. It mirrors how cable actually worked, which is worth something for
a box pretending to be a television.

### Sub-channels are flat, not hierarchical

Nick Jr, Nick and Nick Action are three ordinary channels that happen to sit on
adjacent numbers. **Not** a two-tier guide where you pick Nickelodeon and then
pick again.

Brian's call, and his reasoning was better than the alternative: flat is simpler
to navigate and spreads shows across more channels, which is what makes it feel
like television rather than a menu.

This is also what brings age and format back in without breaking the one-folder
rule — Nick Jr is the preschool one, Nick Action is the older one.

### The guide must scroll

Brian's call. Phase 1's grid caps at five columns and has no paging; past about
twenty channels the tiles get too small to read from a sofa. Scrolling lifts that
ceiling and is what makes a lineup this size possible at all.

### The library is for now *and* later

Keeping Dragon Ball Z (10+) and Avatar (7+) settles a question that was open:
the box will carry content well above a 2-year-old. **Some channels must be ones
a small child cannot stumble onto.** That is now a design requirement, not a
preference.

The `•` random button makes this sharper, not softer — it is the control most
likely to be pressed by the youngest user and the one most likely to find
something upsetting.

---

## Recommended, not yet chosen

### Two-digit numbers in family blocks

Every channel is two digits, 10–99. Each network family owns a decade:

| Block | Family |
|---|---|
| 1x | Preschool (Teletubbies, Barney, Plaza Sésamo, Pocoyó, Daniel Tiger) |
| 2x | Nickelodeon (Nick Jr, Nick, Nick Action) |
| 3x | Cartoon Network (CN Classics, CN) |
| 4x | Disney (Disney Jr, Disney, Disney Action) |
| 5x | Warner Bros (Looney Tunes, Scooby, DC) |
| 6x | Anime (Anime Kids, Anime Action) |
| 7x | Streaming (Apple Kids, Netflix Kids, Prime Kids) |
| 8x | Cine (by studio) |
| 9x | Televisa / Mexico |

**Why two digits everywhere rather than a mix.** No channel number is a prefix
of another, so every tune is exactly two presses with no pause, ever. A mixed
scheme reintroduces the wait: with both channel 2 and channels 20–29 present,
typing `2` cannot commit until the box knows a second digit is not coming.

That waiting behaviour was fixed on 2026-08-20 (`_entry_could_grow` in
`app.py`) so the box only waits when a longer channel genuinely could follow.
All-two-digit means it never has to.

**The cost:** "Arthur is 4" becomes "Arthur is 14". Slightly harder for a
4-year-old to memorise — though with tile artwork and the random button, the
number pad is probably Brian's route rather than theirs.

### One deliberate exception: a Calm channel

Sixteen shows are rated `Calm` in the lineup — the whole streaming block plus
Teletubbies, Barney and Pocoyó. Enough to fill a channel on their own.

A **Calm** channel cutting across networks would break network-primary, and it
is probably worth it: it is the most useful channel on the box for a wind-down
hour, and the safest thing to leave a 2-year-old with. It also gives Phase 3's
parked bedtime sign-off something to do — restrict to Calm rather than only
warning and stopping.

Cost: those shows are then not on their network's channel, because a show lives
in one folder. Symlinks would work on the USB drive but add a failure mode.

---

## Open

- **The numbering itself.** Two-digit blocks is a recommendation Brian has not
  accepted or rejected.
- **Netflix and Prime are thin** — three shows and two. As their own channels
  they would feel empty. Merging them into one calm-preschool channel is the
  obvious fix and is the same decision as the Calm channel above.
- **How a channel is kept away from a small child.** Numbering alone does not do
  it: any number can be typed. Options not yet explored — the random button
  excluding channels above an age, or the guide hiding them, or nothing at all.

---

## How the guide pages

Built 2026-08-20. **Paged, a screenful at a time**, not cursor-driven scrolling.

The spec above framed this as smooth-versus-simple and leaned cursor-driven.
That undersold paging for these users. With pages, a channel is always in the
same place on the same page: Nick Jr is forever "top row, third along, page
one". Cursor-driven scrolling puts a channel wherever your approach left it, so
its position is never twice the same. Neither child can read the labels, so
position is most of what they have, and it matters more once Phase 2 puts
artwork on the tiles.

**A page is four across and two down** - eight channels. Of the shapes that fit
the canvas, it gives the largest tiles: 264x305 with the show name at 29px, half
again as tall as the 5x4 grid seventeen channels would otherwise produce. Both
numbers are dials (`guide.page_cols`, `guide.page_rows`) because tile size can
only be judged on a television.

**A lineup that fits on one page is unaffected.** Paging switches on only when
the lineup outgrows a page; below that the guide keeps the roughly-square
`grid_shape` layout it always had. Verified byte-for-byte against the previous
code: drawing and cursor movement are identical for one to eight channels, and
diverge from nine.

Movement follows the page:

- Left and right walk the whole lineup in reading order, exactly as before,
  carrying onto the next page at the edge.
- Down from the bottom row lands on the next page in the same column; up from
  the top row lands on the previous page's bottom row. Both wrap.
- Arriving on the part-full last page in a column that has no tile settles on
  the last real tile rather than an empty cell.

**A row of dots along the bottom** shows which page you are on, one per page,
the current one bright. Not "PAGE 2 OF 3": nobody in the house can read that
yet. The dots get a reserved strip out of the tile area, so a name and a dot can
never be drawn over each other.

## What the lineup produces

Eleven families, roughly seventeen sub-channels once populated. Well past the
ten-button number pad, and past the point where the current guide grid stays
readable — which is why scrolling is a real build rather than a nicety.

Source of truth for the lineup is the spreadsheet, not this document:
<https://docs.google.com/spreadsheets/d/17ZosBycj-9h-rPOxlbyKl0ZbghPSSr87pUSzDdKmjAo/edit>

---

## Facts from the code that bear on this

- **Channel numbers can already be three digits.** `_digit_buffer` holds three
  characters, so 0–999 works today with no change.
- **Digit entry commits as soon as it is unambiguous** — it only waits while a
  longer channel number starts with what has been typed.
- **The guide grid is `cols = min(5, ceil(sqrt(n)))`, rows round up.** Comfortable
  to about 12 channels, tight at 16–20, name text too small to read past 25.
- **Dedicated CH/VOL buttons keep working while the guide is open.** That is what
  splitting the d-pad off from them bought.
- **`grid_shape` guarantees every cursor move lands on a real channel**, including
  in a ragged last row.
