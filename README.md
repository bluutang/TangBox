# TangBox

**A Raspberry Pi that turns folders of old kids' shows into real TV channels.**

Flip to channel 4 and a show is already playing, a few seconds in, like you just
walked into the room and turned the TV on. When the episode ends the next one
rolls automatically, forever, on shuffle. There's a green channel banner, a
volume bar, a curved CRT picture and a burst of static when you change channels.

No menus. No apps. No touchscreen. A remote and channels, the way TV worked in
1999.

TangBox is a fork of [landonbtw/NostalgiaBox](https://github.com/landonbtw/NostalgiaBox),
adapted for the **Raspberry Pi 5**. See [Staying in sync](#staying-in-sync-with-the-original)
for how to pull the original author's fixes.

---

## 1. Hardware

The original project was written for a Pi 4. This fork runs on a **Pi 5**, and
three of the parts are genuinely different. Buying the Pi 4 versions will cause
real problems, so this table is the one to shop from.

| Part | Notes | Rough cost |
|------|-------|-----------|
| **Raspberry Pi 5** | The brain. 4GB is plenty. | *(already owned)* |
| **Official 27W USB-C power supply** | ⚠️ **Not the Pi 4 supply.** The Pi 5 wants 5V/5A. An underpowered Pi browns out under load, and brownouts corrupt SD cards. | ~$12 |
| **Pi 5 case with a fan** | ⚠️ **A Pi 4 case will not fit.** The Pi 5 also runs hot enough that Raspberry Pi themselves recommend active cooling. The official case has a fan built in; the Argon NEO 5 is a good alternative. | ~$15–25 |
| **Micro SD card, 32GB, A1 or A2** | Holds the operating system and TangBox — **not** the shows (those live on the USB drive below). Actual usage is ~3GB; 32GB is for headroom and because sub-32GB cards are mostly off-brand now. **The A1/A2 rating is the spec that matters** — see below. | ~$9 |
| **USB 3.0 flash drive** | Holds the episodes. Size to your library: ~12MB per minute of SD-quality video, so 128GB ≈ 154 hours. Cheaper per GB than an SD card. Into a **blue** USB 3.0 port. | ~$15 (128GB) |
| **Micro-HDMI → HDMI cable** | Same as the Pi 4. The Pi 5 also uses micro-HDMI. Use the port **nearest the power connector** (HDMI0). | ~$8 |
| **Flirc USB adapter** | Lets any IR remote drive the box. Optional if you use your TV's remote instead (see below). | ~$25 |
| **Simple big-button remote** | The one the kids will actually use. | ~$15 |

You'll also need a TV with HDMI, a computer to set up the SD card, and your own
video files.

### Choosing the SD card: ignore the big number on the front

Cards advertise **sequential** speed — V30, "170 MB/s", UHS-II. That's the figure
that matters for a camera writing one continuous stream. An operating system does
the opposite: thousands of tiny scattered reads.

The rating for that is the **Application Performance Class**, the small `A1` or
`A2` badge:

| Class | Random read | Random write |
|---|---|---|
| A1 | 1,500 IOPS | 500 IOPS |
| A2 | 4,000 IOPS | 2,000 IOPS |

A "fast" V30 card with no A rating can feel sluggish booting a Pi while a humbler
A1 card feels quick. Since the shows live on USB, running the OS is this card's
only job — which is exactly the workload the A rating measures.

**Don't pay for UHS-II or UHS-III.** The Pi 5's reader tops out at UHS-I SDR104,
about 104 MB/s. A faster card just runs at that ceiling.

A1 is genuinely fine. A2 is a modest gain on a Pi 5 and worth it only if the price
gap is a dollar or two. Buy from a seller you trust — counterfeit cards are common
on marketplace listings.

### About the remote: you may not need to buy one

TangBox supports **HDMI-CEC**, which means your TV's own remote can drive it
straight through the HDMI cable. That costs nothing and is already built in
(`input: cec: true`).

The trade-off is that CEC support varies a lot between TV brands, and a
dedicated big-button remote is genuinely better for small kids, since there are
fewer wrong buttons to press. Try CEC first; the Flirc is the fallback.

### One thing that sounds alarming and isn't

The Pi 5 **removed the hardware H.264 video decoder** that the Pi 4 had. H.264 is
the format most video files use, so this sounds like a dealbreaker.

It isn't. The Pi 5's processor is fast enough to decode 1080p H.264 in software
using roughly 20% of the CPU, and old kids' shows are almost always
standard-definition, which is far easier still. TangBox already asks the player
to fall back gracefully. No configuration needed.

---

## 2. Working on it from a computer

You can develop and check everything on a Mac or PC without any hardware — but
**you cannot watch it there.** See
[Checking the running order without a screen](#checking-the-running-order-without-a-screen)
for why, and what to do instead. Video works on the Pi and only on the Pi.

```bash
brew install mpv ffmpeg
cd tang-box
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]" python-mpv     # note: NOT ".[pi]" on a Mac
.venv/bin/pytest                                 # the full test suite
.venv/bin/tangbox --check                        # lists your channels
scripts/simulate.py                              # prints the running order
```

`evdev` is deliberately left out on a Mac. It reads Linux input devices and
won't build on macOS, which is why the command above installs `.[dev]` plus
`python-mpv` rather than the `.[pi]` bundle the Pi uses.

**Keys on the real box** (and via the `stdin` input backend on a Linux terminal):

| Key | Does |
|---|---|
| ↑ / ↓ | Change channel |
| ← / → | Volume down / up (`-` and `+` also work) |
| `2`, `3`, `4`… | Jump straight to that channel number |
| `m` | Mute |
| `i` | Info |
| `l` | Last channel |
| `q` or `Esc` | Quit |

If you keep a local `config.yaml` for development, one setting matters:
`power_off_on_min_volume: false`. On the Pi, pressing volume-down again at zero
powers the box off; on a Mac it would try to shut down your computer.

---

## 3. Setting up the Pi

### Part A — Write the SD card

Install the **Raspberry Pi Imager** from
[raspberrypi.com/software](https://www.raspberrypi.com/software/), then insert
the micro SD card.

Imager (verified against **v2.0.11**) is a wizard with six steps listed down the
left: **Device → OS → Storage → Customisation → Writing → Done**. You click
**NEXT** to move through them.

1. **Device** — pick **Raspberry Pi 5**. Its line reads "Raspberry Pi 5, 500 /
   500+, and Compute Module 5".
2. **OS** — pick **Raspberry Pi OS Lite (64-bit)**, filed under
   "Raspberry Pi OS (other)". "Lite" has no desktop, which is what you want:
   this box boots straight to the TV and never shows a desktop.
3. **Storage** — pick your SD card. Check the size shown matches the card, since
   this step erases whatever it points at.
4. **Customisation** — the important one, and itself six sub-steps listed under
   "Customisation" in the sidebar. **Never click "Skip customisation"**, whatever
   the label suggests: it discards everything and produces a Pi you cannot reach.

   | Sub-step | What to set |
   |---|---|
   | **Hostname** | `tangbox` |
   | **Localisation** | Capital city, time zone, keyboard layout — see below |
   | **User** | Username (e.g. `brian`) and a password. **Write the password down; there is no recovery.** This same password is what SSH and `sudo` use later. |
   | **Wi-Fi** | Network name and password. Leave "Hidden SSID" unticked unless your network really is hidden. |
   | **Remote access** | **Enable SSH**, with "Use password authentication". No password is asked for here — it uses the one from the User step. |
   | **Raspberry Pi Connect** | Skip. It's a cloud service needing a Raspberry Pi account, and you reach the Pi over your own network. |

   **On Localisation:** the "Capital city" list contains only capital cities, so
   there is no Los Angeles or New York — pick **Washington, D.C. (United
   States)** to get the `us` keyboard layout, then **set the Time zone field
   yourself** (e.g. `America/Los_Angeles`). Washington otherwise leaves you on
   Eastern time. The two fields are independent and overriding the zone is
   expected.

   Getting the zone right matters more than it looks: the Pi has **no
   battery-backed clock** and reads the time off the network at every boot, so
   this setting is how it interprets it.

   There is **no "Wi-Fi country" field** in Imager 2.0.11. Older versions had
   one; the country now comes from your Localisation choice.

   This step is the entire bootstrap. The Pi has no keyboard or monitor of its
   own, so what you type here is the only way it can join your network, and the
   only way you can reach it afterwards. A card written without it produces a Pi
   that boots and is then genuinely unreachable, and the only fix is to write the
   card again from scratch.

5. **Writing** — let it run, then eject the card. Imager reports the write speed;
   anything under ~20 MB/s means an old or slow card.

### Part B — Assemble

1. Pi into the case, with the fan connected.
2. Flirc adapter into a USB port (skip if you're trying CEC first).
3. USB drive with the shows into one of the **blue** USB 3.0 ports.
4. Micro-HDMI cable from the Pi's **HDMI0** port (nearest the power connector)
   to the TV.
5. SD card in.
6. Power in. Give it about a minute.

### Part C — Connect from your computer

Open Terminal on a Mac, or PowerShell on Windows:

```bash
ssh YOUR_USERNAME@tangbox.local
```

Type `yes` the first time, then your password. The screen stays blank while you
type the password. You're in when the prompt reads something like
`brian@tangbox:~ $`.

If `tangbox.local` doesn't resolve, find the Pi's IP address in your router's
device list and use that instead.

### Part D — Install TangBox

```bash
sudo apt update
sudo apt install -y git
git clone https://github.com/bluutang/TangBox.git
cd TangBox
./scripts/install.sh
```

This installs the media player (mpv), video tools (ffmpeg), the retro font and
everything else. It takes several minutes. It's finished when you see
`==> Done!`.

### Part E — Load your shows on the USB drive

One folder per channel. Build this on your Mac, in `~/Movies/TangBox/`, then copy
it to the USB drive:

```
Dragon Tales/
├── S01E01.mp4
└── S01E02.mp4
Arthur/
The Magic School Bus/
```

Season sub-folders inside a show folder are fine. Recognised types: `.mp4`,
`.mkv`, `.avi`, `.m4v`.

**Commercials are optional.** Drop advert clips into a `_commercials/` folder
alongside the shows and the station will go to break between episodes. The
leading underscore matters: it's what stops the folder being treated as a
channel. No folder means no breaks, and everything behaves as if the feature
didn't exist.

```
_commercials/
├── cereal-1997.mp4
└── toy-robot-1999.mp4
```

Breaks are built by **length**, not by count — adverts run anywhere from 15 to 60
seconds, so a fixed count would give a 45-second break one time and three minutes
the next. `break_seconds` in the config sets the target (75 by default), which
works out at two or three clips. Every advert airs once before any repeats.

The Internet Archive has large collections of vintage TV commercials, often as
complete ad breaks already assembled.

**Format the drive as exFAT.** It's the one common format both macOS and Linux
read and write properly, which is the whole point — you'll be adding episodes
from your Mac for years. (ext4 is the Linux-native choice, but macOS can't write
to it without extra software.)

Then teach the Pi to mount it. **This step is required**: we installed Raspberry
Pi OS *Lite*, which has no desktop, and it's the desktop that normally auto-mounts
drives. On Lite, plugging a drive in does nothing by itself.

```bash
# exFAT support (not installed by default)
sudo apt install -y exfat-fuse exfatprogs

# Find the drive's UUID - look for your drive by size
sudo blkid

# Make the mount point
sudo mkdir -p /media/tangbox
```

Then add one line to `/etc/fstab` (`sudo nano /etc/fstab`), using the UUID you
just found:

```
UUID=XXXX-XXXX  /media/tangbox  exfat  ro,nofail,uid=1000,gid=1000  0  0
```

Mount it now without rebooting, and check:

```bash
sudo mount -a
ls /media/tangbox
```

Three details in that line worth understanding:

- **`UUID=`** rather than `/dev/sda1`, because device names shuffle between boots.
- **`ro`** mounts it **read-only**. TangBox only ever reads episodes, so this
  costs nothing and means a yanked power cable can't corrupt the drive — the same
  protection Part J gives the SD card, which wouldn't otherwise cover it. You
  still unplug the drive and write to it freely on your Mac.
- **`nofail`** so the Pi still boots normally if the drive isn't plugged in.

**Adding shows later** is then the easy part, and the reason for this setup:
unplug the drive, drag episodes on from your Mac in Finder, plug it back in. No
SSH, no turning Part J's protection off, no reboot.

### Giving a show a picture

Neither of the children this box was built for can read yet, so the channel
guide's tiles carry a picture of each show as well as its name.

Put a **`tile.jpg`** in the show's own folder, beside its seasons:

```
Nick Jr/                 <- the channel
├─ Rugrats/              <- the show
│  ├─ tile.jpg           <- the picture
│  ├─ Season 01/
│  └─ Season 02/
└─ Blue's Clues/
   ├─ tile.jpg
   └─ Season 01/
```

Keeping it inside the show folder means it travels with the media: copy a show
to a new drive and its picture goes too. `tile.png` works as well.

**Supply 4:3 images, 1024x768.** A tile's picture area is 264x198 on the box's
1280x720 canvas, which is exactly 4:3 — the same shape as the programmes
themselves. That is 396x432 on a 1080p television, so 1024x768 has room to
spare and scales down cleanly. Artwork that is not 4:3 is cropped to fill,
centred, rather than letterboxed.

**A show with no picture keeps the old tile**: a large channel number with the
show's name under it. So pictures can be added one show at a time, and a box
with none looks exactly as it always has.

The picture shown is for the programme that channel would play **if you tuned
to it** — which is what you get if you then press OK.

> The Pi needs Pillow for this: `pip install Pillow` (or `pip install .[pi]`,
> which now includes it). Without it the box quietly draws no pictures at all,
> which is worth knowing if your first `tile.jpg` appears to do nothing.

### Part F — Set up your channels

Your channel lineup is already written, in `config.pi.yaml`, and came down with
the `git clone`. Make it the live config:

```bash
cp config.pi.yaml config.yaml
```

Channel numbers in it are **pinned by hand**, at 2, 4, 6 and 8. That's
deliberate. The alternative is `media_root`, which discovers folders
alphabetically and looks tidy right up until you add a show, at which point
every channel silently renumbers and the show your kids know as channel 4
becomes something else. Leaving the odd numbers free means a new show slots in
without disturbing anything.

Edit it whenever the lineup changes:

```bash
nano config.yaml
```

Check your work:

```bash
tangbox --check
```

It prints every channel and how many episodes it found. A channel showing
`NO EPISODES FOUND` means the path is wrong or the file extensions aren't
recognised.

### Part G — Audio over HDMI

The Pi may default to the wrong output. List what's available:

```bash
tangbox --list-audio
```

Pick the HDMI entry and put it in `config.yaml`. On a Pi 5 it usually looks
like:

```yaml
audio_device: "alsa/hdmi:CARD=vc4hdmi0,DEV=0"
```

Use `vc4hdmi1` if you plugged into the second HDMI port.

### Part H — Program the remote

Skip this if you're using your TV's remote over CEC.

1. Unplug the Flirc from the Pi and plug it into your computer.
2. Install the Flirc app from [flirc.tv](https://flirc.tv/).
3. Choose **Full Keyboard** and map your remote's buttons:

| Remote button | Map to |
|---|---|
| Channel up | **Up arrow** |
| Channel down | **Down arrow** |
| Volume up | **Right arrow** |
| Volume down | **Left arrow** |
| Mute | `m` |
| Power | `p` |

Up/down for channel and left/right for volume is the layout the code actually
uses, and it matches how the TV-remote (CEC) path behaves too.

4. Move the Flirc back to the Pi.

If a button does something unexpected, `sudo evtest` on the Pi shows you the key
name it's actually sending, and `input: key_overrides:` in `config.yaml` lets
you remap it.

### Part I — Boot straight to TV

```bash
./scripts/install.sh --service
```

From now on, power on the Pi and it goes straight to the TV. Useful commands:

```bash
systemctl status tangbox       # is it running?
journalctl -u tangbox -f       # live logs
sudo systemctl stop tangbox    # stop it
```

### Part J — Protect the SD card

Kids will pull the plug. Without protection, that can corrupt the SD card.

```bash
sudo raspi-config
```

Go to **Performance Options → Overlay File System** and enable it. The system
then runs from memory and never writes to the card, so yanking the power is
harmless.

Turn it **off** again before making any changes (config edits, new shows,
updates), then back on when you're done. Changes made while it's on are
discarded at reboot.

---

## Staying in sync with the original

This is a fork, so you can pull the original author's bug fixes:

```bash
git fetch upstream
git merge upstream/main
```

Two things make this mostly painless:

- The internal Python package is deliberately still named `nostalgiabox`, even
  though the command you type is `tangbox`. Renaming it would make every
  upstream fix land on a file path that no longer exists here.
- The rebranding is confined to `scripts/`, `pyproject.toml`, this README and a
  handful of display strings.

The README is the one file likely to conflict, since this version is rewritten
for the Pi 5. When it does, keep this one.

---

## Credits

Original project: [NostalgiaBox](https://github.com/landonbtw/NostalgiaBox) by
landonbtw. MIT licensed, same as this fork.

---

## Checking the running order without a screen

There is **no video preview on a Mac**. libmpv driven from Python cannot create a
window on macOS: its Mac renderer needs a Cocoa event loop on the main thread,
which the `mpv` command sets up for itself and a plain Python process does not.
Every video output returns "no vo". This does not affect the Pi, where libmpv
draws straight to the framebuffer with no window system involved.

So on a computer you read the running order instead of watching it:

```bash
scripts/simulate.py                          # 20 items from config.yaml
scripts/simulate.py --config config.pi.yaml  # check the Pi's lineup
scripts/simulate.py --channel-up-at 6        # flip channels part-way through
```

```
  SHOW  S01E03                       [CH 2 Arthur]
  AD    ad-juice-20s
  AD    ad-sneakers-30s
  SHOW  S01E02                       [CH 2 Arthur]
```

Every decision there is made by the same code that runs the television; only the
drawing is missing. It exits non-zero when no channel has any episodes, so it
doubles as a "did I point this at the right folders?" check.
