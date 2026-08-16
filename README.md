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
| **Micro SD card, 128GB, A2-rated** | Holds the OS *and* your episodes. An SD-quality 22-minute episode is roughly 200–400MB, so 128GB is about 350–600 episodes. A2 rating matters for responsiveness. | ~$18 |
| **Micro-HDMI → HDMI cable** | Same as the Pi 4. The Pi 5 also uses micro-HDMI. Use the port **nearest the power connector** (HDMI0). | ~$8 |
| **Flirc USB adapter** | Lets any IR remote drive the box. Optional if you use your TV's remote instead (see below). | ~$25 |
| **Simple big-button remote** | The one the kids will actually use. | ~$15 |

You'll also need a TV with HDMI, a computer to set up the SD card, and your own
video files.

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

## 2. Try it on your Mac first

You don't need any hardware to see what you're building. This runs the whole
thing in a window on your computer, driven by your keyboard.

```bash
brew install mpv ffmpeg
cd tang-box
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]" python-mpv     # note: NOT ".[pi]" on a Mac
.venv/bin/tangbox --generate-assets              # makes the static/colour-bars clips
.venv/bin/tangbox --check                        # lists your channels
.venv/bin/tangbox                                # starts the TV
```

`evdev` is deliberately left out on a Mac. It reads Linux input devices and
won't build on macOS, which is why the command above installs `.[dev]` plus
`python-mpv` rather than the `.[pi]` bundle the Pi uses.

**Keys, while the terminal window has focus:**

| Key | Does |
|---|---|
| ↑ / ↓ | Change channel |
| ← / → | Volume down / up (`-` and `+` also work) |
| `2`, `3`, `4`… | Jump straight to that channel number |
| `m` | Mute |
| `i` | Info |
| `l` | Last channel |
| `q` or `Esc` | Quit |

Two settings in the local `config.yaml` exist purely for Mac testing:

- `fullscreen: false` — keeps the video in a window so it doesn't cover the
  terminal, which is what reads your keypresses.
- `power_off_on_min_volume: false` — on the Pi, pressing volume-down again at
  zero powers the box off. On a Mac it would try to shut down your computer.

Both flip back to the normal values on the Pi.

---

## 3. Setting up the Pi

### Part A — Write the SD card

1. Install the **Raspberry Pi Imager** from
   [raspberrypi.com/software](https://www.raspberrypi.com/software/).
2. Insert the micro SD card.
3. In the Imager choose:
   - **Device:** Raspberry Pi 5
   - **Operating System:** *Raspberry Pi OS Lite (64-bit)*, under
     "Raspberry Pi OS (other)". "Lite" has no desktop, which is what you want,
     since the box boots straight to the TV.
   - **Storage:** your SD card
4. Click **Next → Edit Settings** and set:
   - **Hostname:** `tangbox`
   - **Enable SSH**, using password authentication
   - **Username and password** (write these down)
   - **Wi-Fi** name and password
5. Write it, then eject.

### Part B — Assemble

1. Pi into the case, with the fan connected.
2. Flirc adapter into a USB port (skip if you're trying CEC first).
3. Micro-HDMI cable from the Pi's **HDMI0** port (nearest the power connector)
   to the TV.
4. SD card in.
5. Power in. Give it about a minute.

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

### Part E — Load your shows

One folder per channel:

```
/media/tangbox/
├── Dragon Tales/
│   ├── S01E01.mp4
│   └── S01E02.mp4
├── Arthur/
└── The Magic School Bus/
```

Copy them onto the Pi over the network, or put them on a USB drive and plug it
in. Season sub-folders inside a show folder are fine.

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
