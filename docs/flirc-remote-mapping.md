# Programming the Flirc for TangBox

**Remote:** GE Big Button Universal, **2-device**, model 83036 (charcoal).
**Written 2026-08-20.** Every keystroke below was checked against
`nostalgiabox/input/keymap.py`, not written from memory. If a button ever stops
working, that file is the authority.

## How this works

The Flirc is a USB dongle that **learns infrared and reports itself as a USB
keyboard**. You teach it once, on any computer, and the mapping lives in the
dongle — not on the Pi. So this whole job can be done at the Mac with the Pi
switched off, and the dongle then works in whatever machine you plug it into.

Because any button can send any keystroke, **the printing on the buttons is
irrelevant.** We choose what each one does.

## It fits

**28 buttons taught. 1 held back** (`✱`, for the bedtime sign-off, not built
yet). **3 never touched** (`SETUP`, `TV`, `AUX`). Nothing the box can do is left
unreachable.

## Do this first: put the remote in AUX mode

Program **`AUX`** to a brand you do not own, and teach the Flirc only those
codes. `AUX` then drives TangBox and `TV` drives the television.

Without this, one press talks to both at once — channel-up would change TangBox
*and* the telly.

> ⚠️ **This creates a mode the kids can get lost in.** If someone presses `TV`,
> the number buttons drive the television instead of TangBox and nothing works
> as expected until `AUX` is pressed again. Worth watching. Since TangBox now
> switches the TV on and off by itself over CEC and the input stays on HDMI 3,
> the `TV` side may never be needed at all in normal use.

### Choose a cable or satellite code. Never an audio one.

The Flirc does not learn what a code *means* — it learns the shape of the
infrared flash and staples a keystroke to it, so brand and device type are
irrelevant to the dongle. What is not irrelevant: **a universal remote only
emits infrared for buttons its code set defines.** Press one the code set has no
meaning for and nothing comes out at all — no flash, nothing to learn. The
category decides how much of the keypad is alive.

| Category | Verdict |
|---|---|
| **Cable / satellite** | Best. The fullest keypad: digits, arrows, OK, menu, guide, info, channel, volume, and the `•` dot, which exists as the sub-channel separator for numbers like 5.1. |
| TV | Same coverage, but some televisions answer to other brands' generic codes. A satellite code the Samsung has never heard of cannot. |
| DVD / VCR | Avoid — no sub-channel dot. |
| Audio / receiver | Worst. Amplifiers have no arrows, no channel up/down, no guide and no dot. |

The `•` dot is the button that matters most (see below), and it is silent under
a DVD or audio code. That alone decides the category.

Whether `AUX` accepts every category on the 83036 is **unconfirmed** — it varies
between GE models. If it rejects all cable codes, use whatever it does take and
expect some dead buttons.

### Check the keypad before teaching 27 buttons

Point the remote at a phone's **front-facing** camera and open the camera app.
Front cameras usually do not filter infrared, so the LED appears on screen as a
pale purple-white flash whenever a button genuinely emits something. Press the
awkward ones — `•`, 🏠, ☰, the arrows, `CH` ▲/▼. A button that stays dark is one
the Flirc can never learn, and it is much cheaper to find out now.

## The mapping

| Remote button | Teach it | What it does |
|---|---|---|
| `1`–`9`, `0` | `1`–`9`, `0` | Tune straight to that channel |
| ▲ up | Up arrow | Channel up / move the guide cursor |
| ▼ down | Down arrow | Channel down / move the guide cursor |
| ◀ left | Left arrow | Volume down / move the guide cursor |
| ▶ right | Right arrow | Volume up / move the guide cursor |
| **OK** | `Enter` | Tune to the highlighted channel, or open the guide |
| `ENTER` | `Enter` | Same as OK — harmless duplicate |
| 🏠 house | `h` | Open and close the channel guide |
| ☰ hamburger | `i` | The channel banner, now with a progress bar and time left |
| ↰ back | `l` (lowercase L) | Leave the guide, or jump to the previous channel |
| `ch⤸` return | `l` | Same as back — this is the classic "last channel" button |
| `CH` ▲ | `Page Up` | **Always** changes channel, even with the guide open |
| `CH` ▼ | `Page Down` | **Always** changes channel, even with the guide open |
| `VOL` **+** | `=` | **Always** volume, even with the guide open |
| `VOL` **−** | `-` | **Always** volume, even with the guide open |
| 🔇 mute | `m` | Mute |
| **`•`** | `.` (full stop) | ⭐ **Random channel** |
| `INPUT` | `c` | Step the CRT picture effect through its four looks |
| ⏻ power | `p` | Sign-off collapse, TV off, clean shutdown |

### Why the `•` key matters most

The users are 2 and 4, and neither can read. One button that always does
something good, needs no aiming and no reading, may be the only control the
2-year-old ever uses. It is on the number pad next to `0`, it is easy to find by
feel, and the guide spec named this exact key before the remote was chosen.

### What `INPUT` does

It steps the CRT picture effect round a ladder of four looks, naming each one in
the green banner as it goes:

**NONE → SOFT FRAME → GLASS & GRAIN → HEAVY CRT →** (back to NONE)

`GLASS & GRAIN` is read live from `config.yaml`, so whatever is tuned there is
always a rung in its own right and never more than a press away. The box starts
on it.

**Nothing is saved.** A restart returns to whatever the file says, so a child
cannot permanently change how the television looks and the config file stays the
source of truth. A look you fall in love with on the sofa gets written into the
file properly afterwards.

The point is being able to A/B the picture on the actual television while real
footage is playing — the one thing that cannot be judged from a Mac.

### What ☰ shows

The channel number, name, programme and episode — and beneath them a **timeline**:
a progress bar with the playhead, and **how long is left** of what is playing.

```
CH 02
Dragon Tales
Tales from the Playground
━━━━━━━━●──────────  8:12
```

The bar appears **only on ☰**. A channel change flashes the same banner without
it, so tuning looks exactly as it always has — which is what the children see all
evening. When the length cannot be known (the no-signal static loops forever)
nothing is drawn rather than a bar of invented extent.

The dot is a position marker, not a handle. The remote has no seek, so it must
not look draggable.

### Why the hamburger is the info button

There is no dedicated info button on this remote. Left as a second way to open
the guide — which the house already does — the channel banner would have been
unreachable, so there would be no way to ask "what am I watching?" without
changing channel to find out. The hamburger is the only spare that Phase 3 has
not already claimed.

### The two remaining duplicates are deliberate

`OK`/`ENTER` sit next to each other and mean the same thing, and back/`ch⤸` are
two names for "previous channel". The box accepts several keystrokes per action
on purpose, so teach whichever the Flirc GUI makes easiest. Nothing breaks if
you skip one.

## Leave these alone

| Button | Why |
|---|---|
| `SETUP` | Programs the remote itself. Teaching it to the Flirc could make the remote unconfigurable. |
| `TV` / `AUX` | Device selectors. They switch which device the remote talks to; they are not TangBox actions. |
| `✱` star | **Reserved, and unassigned.** The last spare button. Bedtime sign-off is one proposal, not a decision — Brian wants alternatives weighed first. |

> 🔴 **Never teach any button `Esc` or `q`.** Both map to QUIT, which exits
> TangBox. systemd restarts it after about three seconds, so it recovers — but
> it comes back from scratch: black screen, full sign-on, back to channel 2, and
> the place in the episode is lost. There is no reason for that to be reachable
> from a remote a 4-year-old is holding.

## About the power button

`p` gives a **real shutdown**: the picture collapses to a dot, the television is
told to switch off over CEC, and the Pi halts cleanly.

Known and accepted: a halted Pi cuts power to its own USB ports, so the Flirc
stops listening. **The remote cannot switch the box back on.** That needs the
Pi's onboard button or the inline switch, both of which live behind the
television. TangBox is a box you switch on for a session.

## The backup

**`docs/Tangbox-remote.fcfg`** is all 28 buttons, saved off the dongle on
2026-08-21 with the Flirc app's **File → Save Configuration**.

To restore onto a wiped or replacement dongle, load it with **File → Load
Configuration**, or from the command line:

```bash
/Applications/Flirc.app/Contents/Resources/flirc_util loadconfig \
    docs/Tangbox-remote.fcfg
```

Re-save it after teaching or re-teaching any button, or the file quietly drifts
out of date. Note the Flirc GUI holds the dongle over USB, so `flirc_util`
reports `device disconnected` until the app is quit.

## Checking it worked

**On the Mac, with no Pi involved.** Plug the Flirc in, open any text editor,
and press the remote's buttons. The characters should appear — `h` for the
house, `.` for the dot, digits for digits. That alone proves the dongle learned
them.

> ⚠️ **Passing this test is not proof it works on the box.** A keystroke can
> type perfectly here and still do nothing on the Pi if the box has no mapping
> for it. That happened on 2026-08-20 with `h`, which worked when typed at a
> terminal and was a dead button on a remote until `KEY_H` was added. Everything
> in the table above has since been checked against the code.

**Then on the Pi:**

```bash
cat /proc/bus/input/devices          # find the Flirc's exact device name
```

Put that name into `keyboard_name_filter:` in `config.pi.yaml`. **This matters.**
Without it the keyboard backend also binds `pwr_button`, wiring the Pi's own
power button into the remote-control system — so pressing it would blank the
screen as well as shutting down. Nobody intended that.

```bash
sudo systemctl restart tangbox       # after any config change
```
