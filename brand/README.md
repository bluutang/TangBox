# Tangbox brand assets

| File | What |
|---|---|
| `tangbox-logo.svg` | Black wordmark, transparent background |
| `tangbox-logo-white.svg` | White wordmark, for dark backgrounds and the channel guide |
| `tangbox-logo-preview.png` | How they render, on light and dark |

## How these were made

**The lettering is real type, not a trace.** Comfortaa Regular (weight 400),
shaped with HarfBuzz so the `Ta` pair kerns properly, then converted to outlines.
The first attempt traced the letterforms from a PNG with potrace and Brian
spotted the result was very slightly clipped — reproducing from the font removes
both the clipping and the tracing artefacts.

The weight was chosen by measurement rather than eye: the original's stem-to-cap
ratio is 14/131 = 0.107, and allowing ~1px of antialiasing on that 14px stem puts
it on 400 (0.0999) rather than 450 or 500. Tracking of 21.3 units per gap was
then solved for so the total ink width matches the original's 753px exactly.

**The orange is a true `<circle>`**, and deliberately larger than the letter `o`
it replaces — 103px against the ~93px the glyph would occupy — matching the
original, where the fruit bulges past the text.

**The leaves are traced**, because they are bespoke artwork rather than type.

Comfortaa is licensed under the SIL Open Font License; outlines converted to
paths carry no runtime font dependency.

## Colours

| | |
|---|---|
| Orange | `#EF8225` |
| Leaves | `#539B45` |
| Wordmark | `#000000` / `#FFFFFF` |
