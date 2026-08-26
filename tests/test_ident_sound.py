"""Sound on the sign-on and sign-off idents.

The clips themselves are generated and gitignored; the sound is a recording
that cannot be regenerated, so it lives committed in `assets/sounds/` and is
muxed on after each rebuild. Two things about that arrangement can go quietly
wrong, and both are covered here:

* attaching twice - `make-signoff.py` and `--generate-assets` can both run over
  the same file, and a second sound stream would play over the first.
* attaching never - the sound is best-effort by design, so a failure has to
  leave a SILENT BUT PLAYABLE ident rather than a broken one. A box that signs
  off quietly is fine; a box that cannot sign off is not.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from nostalgiabox import static_gen
from nostalgiabox.static_gen import (
    SIGN_OFF_SOUND,
    SIGN_ON_SOUND,
    SOUNDS_DIRNAME,
    attach_sound,
    ensure_sound,
    has_audio_track,
)

pytestmark = pytest.mark.skipif(
    not static_gen.ffmpeg_available(), reason="ffmpeg not installed"
)

SOUNDS = static_gen.DEFAULT_ASSETS_DIR / SOUNDS_DIRNAME


def _audio_streams(path: Path) -> int:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "a",
         "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
        check=False, capture_output=True, text=True,
    )
    return len([ln for ln in out.stdout.splitlines() if ln.strip()])


def _duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        check=False, capture_output=True, text=True,
    )
    return float(out.stdout.strip())


@pytest.fixture
def silent_clip(tmp_path):
    """A short, genuinely silent clip standing in for a freshly built ident."""
    clip = static_gen.generate_static(tmp_path / "clip.mp4", duration=1.0)
    assert not has_audio_track(clip)
    return clip


# -- the shipped files ------------------------------------------------------

def test_both_sounds_are_shipped():
    """They are committed, unlike every mp4 beside them."""
    assert (SOUNDS / SIGN_ON_SOUND).is_file()
    assert (SOUNDS / SIGN_OFF_SOUND).is_file()


@pytest.mark.parametrize(
    "sound_name,clip_name",
    [(SIGN_ON_SOUND, "logo.mp4"), (SIGN_OFF_SOUND, "power_off.mp4")],
)
def test_each_sound_is_cut_to_its_clip(sound_name, clip_name):
    """Alignment is the FILE's business - any lead-in silence is baked in.

    `attach_sound` takes no offset argument precisely because of this, so if a
    sound ever drifts from the length of the clip it belongs to, the sign-off's
    delayed entry would silently slide off the collapse it was timed to.
    """
    clip = static_gen.DEFAULT_ASSETS_DIR / clip_name
    if not clip.is_file():
        pytest.skip(f"{clip_name} is generated and not present in this checkout")
    assert _duration(SOUNDS / sound_name) == pytest.approx(_duration(clip), abs=0.05)


# -- attaching --------------------------------------------------------------

def test_it_gives_a_silent_clip_its_sound(silent_clip):
    assert attach_sound(silent_clip, SOUNDS / SIGN_ON_SOUND) is True
    assert has_audio_track(silent_clip)
    assert _audio_streams(silent_clip) == 1


def test_the_picture_survives_the_mux(silent_clip):
    """The video is stream-copied, so its length must not move."""
    before = _duration(silent_clip)
    attach_sound(silent_clip, SOUNDS / SIGN_ON_SOUND)
    assert _duration(silent_clip) == pytest.approx(before, abs=0.05)


def test_it_never_stacks_a_second_sound(silent_clip):
    """The whole point of the has-audio check in `ensure_sound`."""
    ensure_sound(silent_clip, SIGN_ON_SOUND, static_gen.DEFAULT_ASSETS_DIR)
    ensure_sound(silent_clip, SIGN_ON_SOUND, static_gen.DEFAULT_ASSETS_DIR)
    ensure_sound(silent_clip, SIGN_ON_SOUND, static_gen.DEFAULT_ASSETS_DIR)
    assert _audio_streams(silent_clip) == 1


# -- the ways it is allowed to fail -----------------------------------------

def test_no_sound_file_leaves_the_clip_alone(silent_clip):
    """An install without the sounds folder still gets a working ident."""
    ensure_sound(silent_clip, "nothing-here.m4a", static_gen.DEFAULT_ASSETS_DIR)
    assert not has_audio_track(silent_clip)
    assert silent_clip.is_file()


def test_a_missing_clip_is_not_an_error(tmp_path):
    ensure_sound(tmp_path / "gone.mp4", SIGN_ON_SOUND, static_gen.DEFAULT_ASSETS_DIR)


def test_a_broken_sound_leaves_a_playable_ident(silent_clip, tmp_path):
    """Best-effort: a silent sign-off beats one that will not play."""
    before = _duration(silent_clip)
    junk = tmp_path / "sounds" / "broken.m4a"
    junk.parent.mkdir()
    junk.write_text("this is not audio")

    assert attach_sound(silent_clip, junk) is False
    assert _duration(silent_clip) == pytest.approx(before, abs=0.05)
    assert not list(silent_clip.parent.glob("*.tmp.mp4"))  # tidied up after itself
