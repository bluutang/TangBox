# Programming the Flirc for TangBox

**Written 2026-08-20.** Everything here is derived from the code
(`nostalgiabox/input/keymap.py`), not from memory. If the box ever stops
responding to a button, check that file first — it is the authority.

## How this works

The Flirc is a USB dongle that **learns infrared and reports it as a USB
keyboard**. You teach it once, on any computer, and it remembers: the mapping
lives in the dongle, not on the Pi. So this whole job can be done at the Mac
with the Pi switched off, and the dongle then works in any machine you plug it
into.

Because any button can send any keystroke, **the printing on the remote's
buttons is irrelevant.** We choose what each one does. A button labelled AUX can
send the letter `h` if that is what we want.

## Before you start

The remote is a **GE Big Button Universal (83036)**, chosen because it has a
d-pad, a full number pad, and large buttons a small child can hit.

**Use the GE's two-device feature.** Program `AUX` to a brand you do not own,
and teach the Flirc only those codes. Then `AUX` drives TangBox and `TV` drives
the television. Without this, pressing channel-up would talk to both at once.

You will need: the Flirc dongle, the GE remote, fresh batteries, and the Flirc
GUI app on the Mac.

## The mapping

Work down this table in order. The first block is the one that matters — stop
there if you run out of patience, and the box is already fully usable.

### Essential — do these first

| GE button | Teach this keystroke | What it does |
|---|---|---|
| `0`–`9` | `0`–`9` | Tune straight to a channel |
| d-pad **up** | Up arrow | Channel up (guide closed) / move cursor (guide open) |
| d-pad **down** | Down arrow | Channel down / move cursor |
| d-pad **left** | Left arrow | Volume down / move cursor |
| d-pad **right** | Right arrow | Volume up / move cursor |
| **OK / Select** | `Enter` | Tune to the highlighted channel, or open the guide |
| **Menu** or **Guide** | `h` | Open and close the channel guide |
| **Back / Exit** | `l` (lowercase L) | Leave the guide, or jump to the previous channel |

### Worth doing

| GE button | Teach this keystroke | What it does |
|---|---|---|
| **CH +** | `Page Up` | Always changes channel, even with the guide open |
| **CH −** | `Page Down` | Always changes channel, even with the guide open |
| **VOL +** | `=` | Always volume, even with the guide open |
| **VOL −** | `-` | Always volume, even with the guide open |
| **Mute** | `m` | Mute |
| any spare button | `.` (full stop) | **Random channel.** See the note below |
| **Info** | `i` | Re-show the channel banner |

> ⭐ **Give the random-channel button a big, obvious key.** The users are 2 and
> 4 and neither can read. One button that always does something good, needs no
> aiming and no reading, may be the only control the 2-year-old ever uses. It
> deserves a better button than "whatever was left over".

### The power button — decided 2026-08-20

**Teach it `p`.** Brian's decision: the power button does a real shutdown, and
starting the next session means pressing the Pi's onboard button. TangBox is a
box you switch on for a session, not an always-on appliance.

> ⚠️ **`p` does not do that yet.** Today `p` triggers *standby*: the picture
> stops, a green STANDBY notice sits on screen, and the Pi stays fully on. The
> real shutdown — the one that plays the switch-off zap and halts cleanly —
> exists and works, but the only thing that reaches it today is holding
> volume-down past zero.
>
> Teach `p` anyway. The button is right; what it does behind the scenes is a
> small change still to be made, and making it will not change the mapping.

The intended behaviour, once wired:

| | |
|---|---|
| **Off** | zap collapses to a dot → TV told to standby over CEC → Pi halts cleanly |
| **On** | onboard button → Pi boots → TV woken to HDMI 3 → ident → channel 2 |

Known and accepted: a halted Pi cuts power to its own USB ports, so the Flirc
stops listening. **The remote cannot switch the box back on** — only the Pi's
onboard button or the inline switch, both behind the television.

## Why several keystrokes do the same thing

The box deliberately accepts more than one key per action — `Enter`, `Space` and
`OK` all confirm; `h` and `Menu` both open the guide. Cheap IR remotes report a
grab-bag of codes, so the map is generous on purpose. **Use whichever keystroke
the Flirc GUI makes easiest.** You are not constrained to the one in the table.

## Checking it worked

With the Flirc plugged into the **Mac**, open any text editor and press the
remote's buttons. The characters should appear. That alone proves the dongle
learned them, with no Pi involved.

Then, on the Pi:

```bash
cat /proc/bus/input/devices          # find the Flirc's exact device name
```

Put that name into `keyboard_name_filter:` in `config.pi.yaml`. **This matters.**
Without it the keyboard backend also binds `pwr_button`, which means the Pi's own
power button is wired into the remote-control system — pressing it blanks
TangBox's screen as well as shutting down. Harmless, but nobody intended it.

```bash
sudo systemctl restart tangbox       # after any config change
```
