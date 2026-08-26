# Generated assets

This folder holds the short filler clips the TV uses:

- `static.mp4` — analog "snow" shown briefly when changing channels.
- `colorbars.mp4` — SMPTE colour bars / "no signal" screen for empty channels.
- `logo.mp4` — the station ident, played at sign-on.
- `power_on.mp4` / `power_off.mp4` — the CRT switch-on and the collapse that
  ends the evening.

These are **generated with ffmpeg**, not committed to git. Create them with:

```bash
nostalgiabox --generate-assets
# or
python -m nostalgiabox.static_gen
```

`scripts/install.sh` runs this for you during setup. If the files are missing at
runtime the box still works — channel changes just skip the static burst and
empty channels fall back to a plain "STANDBY" screen.

## `sounds/` — the one thing here that IS committed

`sounds/sign-on.m4a` and `sounds/sign-off.m4a` are recordings. Nothing in this
repo can regenerate them, so unlike every mp4 beside them they are kept in git.

They are muxed onto `logo.mp4` and `power_off.mp4` at the end of asset
generation. Two rules make that safe to run over and over:

- **Each sound is cut to the exact length of the clip it belongs to**, with any
  lead-in silence baked in. The sign-off deliberately starts ~0.8s late so its
  tail fades away over the CRT collapse rather than finishing before it. There
  is no offset parameter anywhere in the code — alignment is the file's job.
- **A clip that already has sound is left alone**, so a second run cannot stack
  a second audio stream on top of the first.

`scripts/make-signoff.py` rebuilds `power_off.mp4` from scratch every run and so
strips its sound; it re-attaches it before it exits. That is the one route by
which the sign-off audio could otherwise vanish without anybody noticing.

Attaching is best-effort throughout. If a sound is missing or unreadable the
ident still plays, just silently — a box that signs off quietly is fine, one
that cannot sign off is not.
