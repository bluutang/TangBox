"""Configuration loading and validation.

The whole box is described by a single YAML file (see ``config.example.yaml``).
This module turns that file into validated :class:`Config` /
:class:`ChannelConfig` objects and fills in sensible defaults so a minimal
config still produces a working television.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional


# Video containers we consider "an episode" when scanning a channel folder.
DEFAULT_VIDEO_EXTENSIONS: tuple[str, ...] = (
    ".mp4", ".mkv", ".avi", ".m4v", ".mov", ".webm", ".mpg", ".mpeg", ".ts",
)


class ConfigError(Exception):
    """Raised when the configuration file is missing or invalid."""


# How a channel behaves the moment you tune into it.
#   random    - start a fresh random episode from the beginning (the default,
#               and what most people picture: flip to the channel, a show
#               starts). Episodes keep rolling on a shuffle after that.
#   resume    - remember where you were on that channel and pick up there,
#               so flipping away and back does not restart the episode.
#   broadcast - the channel behaves like a real station that is "always on":
#               a fixed shuffled running order advances in real time whether
#               or not anyone is watching, so you tune in partway through
#               whatever "would" be airing right now.
TUNE_IN_MODES = ("random", "resume", "broadcast")

# Effect shown briefly while changing channels.
#   glitch - a short burst of digital corruption (default)
#   static - classic analog snow
#   none   - cut straight to the next channel
TRANSITION_EFFECTS = ("glitch", "static", "none")


@dataclass(frozen=True)
class UiConfig:
    """Look of the on-screen overlays (the green digital TV readouts)."""

    font: str = "VT323"             # bundled retro terminal font (OFL)
    color: str = "#4DFF5A"          # bright CRT phosphor green
    dim_color: str = "#123B18"      # unlit volume segment / dot colour
    # VT323 is a PIXEL font with no bold weight of its own, so \b1 makes libass
    # synthesise one by thickening every stroke - which on a pixel font smears
    # the edges and reads as haze. Brian found this on the TV after turning the
    # blur down through 4, 2, 1 and 0 without it ever getting crisp.
    bold: bool = True               # True is the original look; try false on a TV
    # Extra space between glyphs, in VIRTUAL CANVAS pixels (1280x720), so it
    # lands 1.5x wider on a 1080p screen. VT323 sets tightly; opening it up
    # stops adjacent strokes merging at ten feet, which reads as "crisper"
    # before it reads as "wider".
    letter_spacing: float = 0.0
    glow: bool = True               # soft glow around text for that CRT bloom
    glow_blur: float = 4.0          # how soft. See the note below before raising
    # glow_blur is in VIRTUAL CANVAS pixels (1280x720), not screen pixels, so on
    # a 1080p TV it lands 1.5x stronger than it looks on a computer - the same
    # trap that took scanline_intensity from 0.12 down to 0.03. 4.0 is the
    # original value, kept as the default so nobody's box restyles itself.
    # Brian called it hazy on a real TV; try 2 or lower, but judge it on the TV.


@dataclass(frozen=True)
class GuideConfig:
    """The channel guide - the grid you get by pressing Home.

    Both numbers were chosen on paper and can only really be judged on a
    television from across a room, which is why they are dials and not
    constants in the drawing code.
    """

    # Seconds of no input before the guide closes itself. A child who wanders
    # off should not leave the television dimmed under a menu all evening.
    # Zero means "stay open until somebody closes it", the same convention the
    # overlay durations use.
    timeout_seconds: float = 20.0
    # How far the picture behind the guide is dimmed, 0 (not at all) to 1
    # (black). The programme keeps playing underneath either way.
    dim: float = 0.66
    # How many channels fit on one page of the guide, across and down. Once the
    # lineup outgrows a page the guide pages rather than shrinking the tiles,
    # because a name too small to read from a sofa helps nobody. Four by two
    # gives the largest tiles of the shapes that fit, which matters while
    # neither child can read and the picture is doing the work.
    page_cols: int = 4
    page_rows: int = 2


@dataclass(frozen=True)
class SignOnConfig:
    """The station sign-on: colour bars, then a logo, then the first channel.

    How a TV station used to start the broadcast day. It runs EVERY time the box
    is switched on, in front of small children who want cartoons, so it is kept
    short and any button press skips it.
    """

    # OFF by default, on purpose. This changes what happens at power-on, and a
    # new feature should not quietly restyle the first thing anyone sees - the
    # 17 existing tests that broke when it defaulted to True made that point
    # clearly. config.pi.yaml switches it on for the real box.
    enabled: bool = False
    bars_seconds: float = 2.0       # colour bars with the 1 kHz tone
    # Replay the ident when WAKING from standby, not only at boot. Starts at
    # the ident and skips the pre-roll: the pre-roll exists to cover a
    # television waking up, and on a wake the set is already on and showing us.
    #
    # OFF by default, on the same rule as `enabled` - it changes what a button
    # does, and that should be opted into rather than arrive in an update.
    on_wake: bool = False
    logo: str = "logo.mp4"          # asset filename; missing = bars only
    # The CRT switch-on: a dot blooms to a line, the line opens to the frame.
    # Runs FIRST, so it is the very first thing the screen does.
    power_on: str = "power_on.mp4"


@dataclass(frozen=True)
class CrtConfig:
    """The CRT picture effect applied to the 4:3 video via a GLSL shader."""

    enabled: bool = True
    curvature: float = 0.12         # barrel "bulge" amount (0 = perfectly flat)
    corner_radius: float = 0.065    # rounded-corner size (fraction of screen)
    vignette: float = 0.25          # darkening toward the edges
    scanlines: bool = True
    scanline_intensity: float = 0.12


@dataclass(frozen=True)
class CommercialsConfig:
    """Adverts played between episodes, the way a real station went to break.

    ``path`` pointing nowhere (or at an empty folder) simply means no breaks -
    the box behaves exactly as it did before the feature existed.
    """

    enabled: bool = True
    path: Optional[Path] = None
    break_seconds: float = 75.0     # aim for roughly this much advertising
    break_ratio: float = 0.0        # 0 = every break the same length
    break_max_seconds: float = 0.0  # 0 = no ceiling


@dataclass(frozen=True)
class ChannelConfig:
    """A single television channel backed by a folder of episodes."""

    number: int
    name: str
    path: Path
    shuffle: bool = True
    # Episodes to leave out. `exclude` is a list of case-insensitive glob
    # patterns matched against each file's path (and name); `exclude_seasons` is
    # a set of season numbers detected from the path (e.g. S06E01, "Season 6").
    exclude: tuple[str, ...] = ()
    exclude_seasons: frozenset[int] = frozenset()
    # How this channel behaves when tuned into. None means "use the global
    # tune_in". Set it per channel when one channel should differ - a station
    # running to a schedule (broadcast) alongside a film channel that picks up
    # where you left off (resume).
    tune_in: Optional[str] = None
    # Per-channel override of `episode_order`. None means "use the global one".
    episode_order: Optional[str] = None
    # Which subfolder of the commercials folder this channel's bumps live in.
    # None means "generic adverts only", which is right for a channel with no
    # network to imitate - and for Netflix and Apple TV+, which never carried
    # advertising at all.
    commercials: Optional[str] = None

    def __post_init__(self) -> None:
        if self.number < 0:
            raise ConfigError(f"channel number must be >= 0, got {self.number}")
        if not self.name:
            raise ConfigError(f"channel {self.number} is missing a name")


@dataclass(frozen=True)
class Config:
    """Top-level configuration for the whole nostalgia box."""

    channels: List[ChannelConfig]
    video_extensions: tuple[str, ...] = DEFAULT_VIDEO_EXTENSIONS
    tune_in: str = "random"
    # How a channel picks what plays next.
    #   shuffle    - a bag of every episode on the channel  [the old behaviour]
    #   sequential - a bag of SHOWS; each show plays its episodes in order, so
    #                which show you get is a surprise and which episode is not
    episode_order: str = "shuffle"
    start_channel: Optional[int] = None

    # Presentation / "feel" of the TV.
    fullscreen: bool = True                # true on the Pi/TV. Set false to run in
                                          #   a window (useful on a dev Mac, where a
                                          #   fullscreen window would cover the
                                          #   terminal that reads the keys)
    force_4_3: bool = False                # if true, letterbox everything to 4:3;
                                          #   default keeps each show's own aspect
    # Start each episode a random number of seconds in (between min and max), so
    # channel switches land at varied points in the show.
    start_offset_min: float = 6.0
    start_offset_max: float = 10.0
    transition_effect: str = "none"       # channel-change effect: none|glitch|static
    transition_duration: float = 0.4      # length of the channel-change effect
    # When there's no transition effect, keep the current show playing this many
    # seconds while the next channel preloads, then cut over (avoids a frozen
    # frame on channel change). 0 = switch immediately.
    bridge_seconds: float = 0.8
    channel_bug_seconds: float = 4.0      # how long the channel banner lingers
    osd_duration: float = 2.0             # how long volume/message overlays linger
    ui: UiConfig = field(default_factory=UiConfig)
    crt: CrtConfig = field(default_factory=CrtConfig)
    sign_on: SignOnConfig = field(default_factory=SignOnConfig)
    guide: GuideConfig = field(default_factory=GuideConfig)

    # Audio.
    initial_volume: int = 70              # 0-100
    volume_step: int = 5
    audio_device: Optional[str] = None
    # Which HDMI mode mpv should set. None lets mpv pick the connector's
    # PREFERRED mode - which on a 4K TV means 4K, even when the kernel was
    # told otherwise on the cmdline. See config.pi.yaml for why less is more.
    display_mode: Optional[str] = None    # mpv audio device (e.g. HDMI); None = auto
    # Press volume-down once more when already at 0 to cleanly power off the Pi
    # (so it's safe to unplug). The command run to shut down:
    power_off_on_min_volume: bool = True
    power_off_command: tuple[str, ...] = ("sudo", "poweroff")
    # What the remote's POWER button means. "standby" blanks the screen and
    # leaves the Pi running; "shutdown" plays the sign-off collapse and halts
    # the machine properly.
    #
    # Defaults to "standby" so that no existing box changes what its power
    # button does just by taking an update - the same reason the sign-on
    # defaults off in code and is switched on in config.
    #
    # Worth knowing before choosing "shutdown": a halted Pi cuts power to its
    # own USB ports, so an infrared receiver plugged into one stops listening.
    # The remote can switch the box OFF but never back ON.
    power_button: str = "standby"
    # Where the bedtime sign-off ENDS. "shutdown" halts the Pi, which is the
    # honest end of the day but a one-way door: a halted Pi cuts power to its
    # own USB ports, so the infrared receiver stops listening and only the
    # button on the board can bring it back. "standby" keeps the whole ritual
    # - the countdown, the collapse - and simply leaves the box quiet and
    # wakeable, which is what you want if a small child can reach the remote.
    #
    # Defaults to "shutdown" so that no existing box changes what its bedtime
    # button does just by taking an update.
    bedtime_ends_in: str = "shutdown"
    # Play the sign-off collapse when POWER goes to standby, not only at a
    # halt or bedtime. OFF by default: it puts the whole clip in front of every
    # POWER press, which is a trade rather than an obvious win.
    sign_off_on_standby: bool = False
    # Draw the "STANDBY" card once the box has gone quiet. Turn it off to let
    # the sign-off's last frame be the last thing on screen - worth doing where
    # the television switches itself off anyway, less so where it stays on and
    # a black screen is indistinguishable from a crash.
    standby_notice: bool = True
    # How long the sign-off clip is given before playback is stopped. Was a
    # hard-coded 1.1, which silently truncated a longer clip - the mirrored
    # ident sign-off runs about 3.8s.
    sign_off_seconds: float = 1.1
    # Run just before the machine halts, to tell the television to switch off
    # too - e.g. ["sh", "-c", "echo standby 0 | cec-client -s -d 1"]. Empty
    # means "leave the television alone". Best-effort: if it fails, the Pi
    # still halts.
    tv_standby_command: tuple[str, ...] = ()
    # Run when the box comes back ON - waking from standby, or starting up.
    # HDMI-CEC "One Touch Play" both powers the television on AND switches it
    # to this input, e.g.
    #   ["sh", "-c", "echo 'on 0' | cec-client -s -d 1; echo as | cec-client -s -d 1"]
    # Empty means "leave the television alone". Best-effort: a set that will
    # not answer must never stop the box working.
    tv_wake_command: tuple[str, ...] = ()

    # Playback.
    scan_recursive: bool = True           # look in sub-folders for episodes
    shuffle_seed: Optional[int] = None    # set for deterministic ordering (tests)
    commercials: CommercialsConfig = field(default_factory=CommercialsConfig)

    # Assets (generated by scripts/install.sh via nostalgiabox.static_gen).
    assets_dir: Optional[Path] = None

    # Options for the input backends (see input/manager.create_backends).
    input_options: Mapping[str, Any] = field(default_factory=dict)

    def channel_numbers(self) -> List[int]:
        return [c.number for c in self.channels]

    def with_channels(self, channels: List[ChannelConfig]) -> "Config":
        return replace(self, channels=channels)


def _as_path(value: Any, base: Optional[Path]) -> Path:
    p = Path(os.path.expanduser(str(value)))
    if not p.is_absolute() and base is not None:
        p = (base / p)
    return p


def _discover_channels(
    media_root: Path,
    *,
    start_number: int,
    default_shuffle: bool,
) -> List[ChannelConfig]:
    """Turn every immediate sub-folder of ``media_root`` into a channel.

    This is the "just drop show folders on the SD card" workflow: a folder
    called ``Dragon Tales`` becomes a channel named "Dragon Tales". Channels
    are numbered sequentially starting at ``start_number`` in alphabetical
    order of the folder name.
    """
    if not media_root.is_dir():
        raise ConfigError(f"media_root does not exist or is not a directory: {media_root}")

    subdirs = sorted(
        # Skip hidden folders, and folders starting with "_" - that underscore is
        # the convention for content that is not a channel, such as the
        # "_commercials" pool that plays between episodes.
        (
            p
            for p in media_root.iterdir()
            if p.is_dir() and not p.name.startswith((".", "_"))
        ),
        key=lambda p: p.name.lower(),
    )
    channels: List[ChannelConfig] = []
    for offset, folder in enumerate(subdirs):
        channels.append(
            ChannelConfig(
                number=start_number + offset,
                name=_prettify_name(folder.name),
                path=folder,
                shuffle=default_shuffle,
            )
        )
    return channels


def _prettify_name(folder_name: str) -> str:
    """Turn a folder name like ``dragon_tales`` into ``Dragon Tales``."""
    cleaned = folder_name.replace("_", " ").replace("-", " ").strip()
    cleaned = " ".join(cleaned.split())
    return cleaned.title() if cleaned.islower() else cleaned


def _parse_channels(raw: Any, base: Optional[Path], default_shuffle: bool) -> List[ChannelConfig]:
    if not isinstance(raw, list):
        raise ConfigError("'channels' must be a list")
    channels: List[ChannelConfig] = []
    for i, entry in enumerate(raw):
        if not isinstance(entry, dict):
            raise ConfigError(f"channel #{i} must be a mapping, got {type(entry).__name__}")
        if "path" not in entry:
            raise ConfigError(f"channel #{i} is missing required key 'path'")
        number = entry.get("number", i + 2)  # old TVs often started around ch. 2
        name = entry.get("name") or _prettify_name(Path(str(entry["path"])).name)
        channels.append(
            ChannelConfig(
                number=int(number),
                name=str(name),
                path=_as_path(entry["path"], base),
                shuffle=bool(entry.get("shuffle", default_shuffle)),
                exclude=_parse_str_list(entry.get("exclude"), "exclude"),
                exclude_seasons=_parse_seasons(entry.get("exclude_seasons")),
                tune_in=_parse_channel_tune_in(entry.get("tune_in"), i),
                episode_order=_parse_episode_order(
                    entry.get("episode_order"), f"channels[{i}].episode_order"
                ),
                commercials=(
                    str(entry["commercials"]).strip() or None
                    if entry.get("commercials") is not None
                    else None
                ),
            )
        )
    return channels


def _parse_episode_order(raw: Any, where: str) -> Optional[str]:
    """Validate an `episode_order`, or None to inherit the global setting."""
    if raw is None:
        return None
    value = str(raw).strip().lower()
    if value not in ("shuffle", "sequential"):
        raise ConfigError(
            f"'{where}' must be 'shuffle' or 'sequential', got {value!r}"
        )
    return value


def _parse_channel_tune_in(raw: Any, index: int) -> Optional[str]:
    """Validate a per-channel tune_in override. None means 'use the global one'."""
    if raw is None:
        return None
    mode = str(raw).lower()
    if mode not in TUNE_IN_MODES:
        raise ConfigError(
            f"channel #{index}: 'tune_in' must be one of {TUNE_IN_MODES}, got '{mode}'"
        )
    return mode


def _parse_str_list(raw: Any, name: str) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, list):
        return tuple(str(x) for x in raw)
    raise ConfigError(f"'{name}' must be a string or a list of strings")


def _parse_seasons(raw: Any) -> frozenset[int]:
    """Parse season numbers from an int, a 'start-end' range, or a list of those."""
    if raw is None:
        return frozenset()
    items = raw if isinstance(raw, list) else [raw]
    seasons: set[int] = set()
    for item in items:
        if isinstance(item, int):
            seasons.add(item)
        elif isinstance(item, str) and "-" in item:
            lo_s, hi_s = item.split("-", 1)
            try:
                lo, hi = int(lo_s), int(hi_s)
            except ValueError as exc:
                raise ConfigError(f"invalid season range '{item}'") from exc
            seasons.update(range(min(lo, hi), max(lo, hi) + 1))
        else:
            try:
                seasons.add(int(item))
            except (TypeError, ValueError) as exc:
                raise ConfigError(f"invalid season number '{item}'") from exc
    return frozenset(seasons)


def config_from_dict(data: Dict[str, Any], *, base_dir: Optional[Path] = None) -> Config:
    """Build a :class:`Config` from an already-parsed mapping.

    ``base_dir`` is used to resolve relative paths (normally the directory the
    config file lives in).
    """
    if not isinstance(data, dict):
        raise ConfigError("configuration root must be a mapping")

    default_shuffle = bool(data.get("shuffle", True))

    exts = data.get("video_extensions")
    if exts is None:
        extensions = DEFAULT_VIDEO_EXTENSIONS
    else:
        if not isinstance(exts, list) or not exts:
            raise ConfigError("'video_extensions' must be a non-empty list")
        extensions = tuple(e if e.startswith(".") else f".{e}" for e in (s.lower() for s in exts))

    media_root_raw = data.get("media_root")
    media_root = _as_path(media_root_raw, base_dir) if media_root_raw else None

    if "channels" in data:
        channels = _parse_channels(data["channels"], media_root or base_dir, default_shuffle)
    elif media_root is not None:
        channels = _discover_channels(
            media_root,
            start_number=int(data.get("first_channel_number", 2)),
            default_shuffle=default_shuffle,
        )
    else:
        raise ConfigError("configuration must define either 'channels' or 'media_root'")

    if not channels:
        raise ConfigError("no channels found - check 'channels' or the folders under 'media_root'")

    _ensure_unique_numbers(channels)

    tune_in = str(data.get("tune_in", "random")).lower()
    if tune_in not in TUNE_IN_MODES:
        raise ConfigError(f"'tune_in' must be one of {TUNE_IN_MODES}, got '{tune_in}'")

    assets_dir_raw = data.get("assets_dir")
    assets_dir = _as_path(assets_dir_raw, base_dir) if assets_dir_raw else None

    start_channel = data.get("start_channel")
    start_channel = int(start_channel) if start_channel is not None else None

    initial_volume = _clamp_int(data.get("initial_volume", 70), 0, 100, "initial_volume")
    volume_step = _clamp_int(data.get("volume_step", 5), 1, 100, "volume_step")
    audio_device = data.get("audio_device")
    audio_device = str(audio_device) if audio_device else None

    poff_raw = data.get("power_off_command", ["sudo", "poweroff"])
    if isinstance(poff_raw, str):
        power_off_command = tuple(poff_raw.split())
    elif isinstance(poff_raw, list):
        power_off_command = tuple(str(x) for x in poff_raw)
    else:
        raise ConfigError("'power_off_command' must be a string or list of strings")

    power_button = str(data.get("power_button", "standby")).strip().lower()
    if power_button not in ("standby", "shutdown"):
        raise ConfigError(
            f"'power_button' must be 'standby' or 'shutdown', got {power_button!r}"
        )

    sign_off_on_standby = bool(data.get("sign_off_on_standby", False))
    standby_notice = bool(data.get("standby_notice", True))
    sign_off_seconds = _clamp_float(
        data.get("sign_off_seconds", 1.1), 0.0, 30.0, "sign_off_seconds"
    )

    bedtime_ends_in = str(data.get("bedtime_ends_in", "shutdown")).strip().lower()
    if bedtime_ends_in not in ("standby", "shutdown"):
        raise ConfigError(
            f"'bedtime_ends_in' must be 'standby' or 'shutdown', got {bedtime_ends_in!r}"
        )

    wake_raw = data.get("tv_wake_command", [])
    if isinstance(wake_raw, str):
        tv_wake_command = tuple(wake_raw.split())
    elif not wake_raw:
        tv_wake_command = ()
    elif isinstance(wake_raw, (list, tuple)):
        tv_wake_command = tuple(str(x) for x in wake_raw)
    else:
        raise ConfigError("'tv_wake_command' must be a string or list of strings")

    tv_raw = data.get("tv_standby_command", [])
    if isinstance(tv_raw, str):
        tv_standby_command = tuple(tv_raw.split())
    elif isinstance(tv_raw, list):
        tv_standby_command = tuple(str(x) for x in tv_raw)
    elif not tv_raw:
        tv_standby_command = ()
    else:
        raise ConfigError("'tv_standby_command' must be a string or list of strings")

    return Config(
        channels=channels,
        video_extensions=extensions,
        tune_in=tune_in,
        episode_order=_parse_episode_order(
            data.get("episode_order"), "episode_order"
        ) or "shuffle",
        start_channel=start_channel,
        fullscreen=bool(data.get("fullscreen", True)),
        force_4_3=bool(data.get("force_4_3", False)),
        start_offset_min=_offset_range(data)[0],
        start_offset_max=_offset_range(data)[1],
        transition_effect=_valid_transition(data.get("transition", "none")),
        transition_duration=_clamp_float(data.get("transition_duration", 0.4), 0.0, 10.0, "transition_duration"),
        bridge_seconds=_clamp_float(data.get("bridge_seconds", 0.8), 0.0, 10.0, "bridge_seconds"),
        channel_bug_seconds=_clamp_float(data.get("channel_bug_seconds", 4.0), 0.0, 60.0, "channel_bug_seconds"),
        osd_duration=_clamp_float(data.get("osd_duration", 2.0), 0.0, 60.0, "osd_duration"),
        ui=_parse_ui(data.get("ui")),
        crt=_parse_crt(data.get("crt")),
        sign_on=_parse_sign_on(data.get("sign_on")),
        guide=_parse_guide(data.get("guide")),
        initial_volume=initial_volume,
        volume_step=volume_step,
        audio_device=audio_device,
        display_mode=_valid_display_mode(data.get("display_mode")),
        power_off_on_min_volume=bool(data.get("power_off_on_min_volume", True)),
        power_off_command=power_off_command,
        power_button=power_button,
        bedtime_ends_in=bedtime_ends_in,
        sign_off_on_standby=sign_off_on_standby,
        standby_notice=standby_notice,
        sign_off_seconds=sign_off_seconds,
        tv_standby_command=tv_standby_command,
        tv_wake_command=tv_wake_command,
        scan_recursive=bool(data.get("scan_recursive", True)),
        shuffle_seed=(int(data["shuffle_seed"]) if data.get("shuffle_seed") is not None else None),
        commercials=_parse_commercials(data.get("commercials")),
        assets_dir=assets_dir,
        input_options=dict(data.get("input") or {}),
    )


def load_config(path: os.PathLike | str) -> Config:
    """Load and validate a YAML configuration file."""
    import yaml  # imported lazily so importing the package is cheap

    cfg_path = Path(path).expanduser()
    if not cfg_path.is_file():
        raise ConfigError(f"configuration file not found: {cfg_path}")
    try:
        with cfg_path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
    except yaml.YAMLError as exc:  # pragma: no cover - passthrough of parser error
        raise ConfigError(f"could not parse YAML in {cfg_path}: {exc}") from exc

    return config_from_dict(data, base_dir=cfg_path.parent)


def _parse_ui(raw: Any) -> UiConfig:
    if raw is None:
        return UiConfig()
    if not isinstance(raw, dict):
        raise ConfigError("'ui' must be a mapping")
    defaults = UiConfig()
    return UiConfig(
        font=str(raw.get("font", defaults.font)),
        color=_valid_color(raw.get("color", defaults.color), "ui.color"),
        dim_color=_valid_color(raw.get("dim_color", defaults.dim_color), "ui.dim_color"),
        bold=bool(raw.get("bold", defaults.bold)),
        letter_spacing=_clamp_float(
            raw.get("letter_spacing", defaults.letter_spacing), 0.0, 50.0,
            "ui.letter_spacing",
        ),
        glow=bool(raw.get("glow", defaults.glow)),
        glow_blur=_clamp_float(
            raw.get("glow_blur", defaults.glow_blur), 0.0, 20.0, "ui.glow_blur"
        ),
    )


def _parse_guide(raw: Any) -> GuideConfig:
    if raw is None:
        return GuideConfig()
    if not isinstance(raw, dict):
        raise ConfigError("'guide' must be a mapping")
    d = GuideConfig()
    return GuideConfig(
        # Capped at ten minutes: past that it is not really closing itself.
        timeout_seconds=_clamp_float(
            raw.get("timeout_seconds", d.timeout_seconds),
            0.0, 600.0, "guide.timeout_seconds",
        ),
        dim=_clamp_float(raw.get("dim", d.dim), 0.0, 1.0, "guide.dim"),
        # Five is the ceiling the guide's own grid uses (guide.MAX_COLS) -
        # past it the show names stop being readable across a room. One is the
        # floor because a page has to be able to hold something, and zero would
        # be a division by zero on the way to finding out.
        page_cols=_clamp_int(raw.get("page_cols", d.page_cols), 1, 5, "guide.page_cols"),
        page_rows=_clamp_int(raw.get("page_rows", d.page_rows), 1, 5, "guide.page_rows"),
    )


def _parse_sign_on(raw: Any) -> SignOnConfig:
    if raw is None:
        return SignOnConfig()
    if not isinstance(raw, dict):
        raise ConfigError("'sign_on' must be a mapping")
    d = SignOnConfig()
    return SignOnConfig(
        enabled=bool(raw.get("enabled", d.enabled)),
        # Capped at 30s deliberately: nobody wants a five-minute ident before
        # the cartoons, and a typo here would be maddening to diagnose.
        on_wake=bool(raw.get("on_wake", d.on_wake)),
        bars_seconds=_clamp_float(
            raw.get("bars_seconds", d.bars_seconds), 0.0, 30.0, "sign_on.bars_seconds"
        ),
        logo=str(raw.get("logo", d.logo)),
        power_on=str(raw.get("power_on", d.power_on)),
    )


def _parse_crt(raw: Any) -> CrtConfig:
    if raw is None:
        return CrtConfig()
    if not isinstance(raw, dict):
        raise ConfigError("'crt' must be a mapping")
    d = CrtConfig()
    return CrtConfig(
        enabled=bool(raw.get("enabled", d.enabled)),
        curvature=_clamp_float(raw.get("curvature", d.curvature), 0.0, 0.5, "crt.curvature"),
        corner_radius=_clamp_float(raw.get("corner_radius", d.corner_radius), 0.0, 0.3, "crt.corner_radius"),
        vignette=_clamp_float(raw.get("vignette", d.vignette), 0.0, 1.0, "crt.vignette"),
        scanlines=bool(raw.get("scanlines", d.scanlines)),
        scanline_intensity=_clamp_float(
            raw.get("scanline_intensity", d.scanline_intensity), 0.0, 1.0, "crt.scanline_intensity"
        ),
    )


def _parse_commercials(raw: Any) -> CommercialsConfig:
    if raw is None:
        return CommercialsConfig()
    if not isinstance(raw, dict):
        raise ConfigError("'commercials' must be a mapping")
    d = CommercialsConfig()
    path = raw.get("path")
    return CommercialsConfig(
        enabled=bool(raw.get("enabled", d.enabled)),
        path=(Path(str(path)).expanduser() if path else None),
        break_seconds=_clamp_float(
            raw.get("break_seconds", d.break_seconds), 0.0, 600.0, "commercials.break_seconds"
        ),
        break_ratio=_clamp_float(
            raw.get("break_ratio", d.break_ratio), 0.0, 1.0, "commercials.break_ratio"
        ),
        break_max_seconds=_clamp_float(
            raw.get("break_max_seconds", d.break_max_seconds), 0.0, 1800.0,
            "commercials.break_max_seconds",
        ),
    )


def _offset_range(data: Dict[str, Any]) -> tuple[float, float]:
    """Resolve the (min, max) start-offset seconds from the config.

    Accepts ``start_offset`` as a single number or a ``[min, max]`` list, or
    explicit ``start_offset_min`` / ``start_offset_max`` keys.
    """
    if "start_offset_min" in data or "start_offset_max" in data:
        lo = _clamp_float(data.get("start_offset_min", 0.0), 0.0, 3600.0, "start_offset_min")
        hi = _clamp_float(data.get("start_offset_max", lo), 0.0, 3600.0, "start_offset_max")
    else:
        raw = data.get("start_offset", [6.0, 10.0])
        if isinstance(raw, (list, tuple)):
            if not raw:
                raise ConfigError("'start_offset' list cannot be empty")
            lo = _clamp_float(raw[0], 0.0, 3600.0, "start_offset")
            hi = _clamp_float(raw[1] if len(raw) > 1 else raw[0], 0.0, 3600.0, "start_offset")
        else:
            lo = hi = _clamp_float(raw, 0.0, 3600.0, "start_offset")
    return (lo, max(lo, hi))


def _valid_display_mode(value: Any) -> Optional[str]:
    """WIDTHxHEIGHT@RATE, or mpv's own 'preferred'/'highest'.

    Validated rather than passed through because mpv SILENTLY IGNORES a mode it
    cannot parse - which looks exactly like the setting having no effect.
    """
    if value is None:
        return None
    text = str(value).strip()
    if text in ("preferred", "highest"):
        return text
    if re.fullmatch(r"[0-9]{3,5}x[0-9]{3,5}@[0-9]{2,3}", text):
        return text
    raise ConfigError(
        f"'display_mode' must be like 1920x1080@60, or 'preferred'/'highest'; got {value!r}"
    )


def _valid_transition(value: Any) -> str:
    s = str(value).strip().lower()
    if s not in TRANSITION_EFFECTS:
        raise ConfigError(f"'transition' must be one of {TRANSITION_EFFECTS}, got '{value}'")
    return s


def _valid_color(value: Any, name: str) -> str:
    """Validate a ``#RRGGBB`` hex colour string."""
    import re

    s = str(value).strip()
    if not re.fullmatch(r"#?[0-9a-fA-F]{6}", s):
        raise ConfigError(f"'{name}' must be a hex colour like '#4DFF5A', got '{value}'")
    return s if s.startswith("#") else f"#{s}"


def _ensure_unique_numbers(channels: List[ChannelConfig]) -> None:
    seen: Dict[int, str] = {}
    for ch in channels:
        if ch.number in seen:
            raise ConfigError(
                f"duplicate channel number {ch.number} used by "
                f"'{seen[ch.number]}' and '{ch.name}'"
            )
        seen[ch.number] = ch.name


def _clamp_int(value: Any, lo: int, hi: int, name: str) -> int:
    try:
        n = int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"'{name}' must be an integer") from exc
    return max(lo, min(hi, n))


def _clamp_float(value: Any, lo: float, hi: float, name: str) -> float:
    try:
        n = float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"'{name}' must be a number") from exc
    return max(lo, min(hi, n))


__all__ = [
    "Config",
    "SignOnConfig",
    "GuideConfig",
    "ChannelConfig",
    "UiConfig",
    "CrtConfig",
    "ConfigError",
    "load_config",
    "config_from_dict",
    "DEFAULT_VIDEO_EXTENSIONS",
    "TUNE_IN_MODES",
    "TRANSITION_EFFECTS",
]
