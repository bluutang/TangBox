"""The placeholder station ident.

It exists so the sign-on sequence works before any artwork does, and it has one
awkward property: rendering text needs ffmpeg's `drawtext` filter, which needs
libfreetype, which Homebrew's ffmpeg on this Mac does NOT have. Debian's build
on the Pi does.

So the text path cannot be exercised here. What can be, and what these tests
cover, is that the missing filter is detected rather than blundered into -
because an ffmpeg failure inside install.sh would be swallowed by the
`|| echo "(asset generation skipped/failed...)"` and nobody would know.
"""

from __future__ import annotations

import pytest

from nostalgiabox import static_gen
from nostalgiabox.static_gen import LOGO_FILENAME, generate_all, generate_logo

pytestmark = pytest.mark.skipif(
    not static_gen.ffmpeg_available(), reason="ffmpeg not installed"
)


def test_it_produces_a_playable_file_without_drawtext(tmp_path, monkeypatch):
    """The fallback must still yield a real clip, not an empty file."""
    monkeypatch.setattr(static_gen, "drawtext_available", lambda: False)
    out = generate_logo(tmp_path / "logo.mp4", duration=1.0)
    assert out.is_file()
    assert out.stat().st_size > 1000


def test_it_uses_drawtext_when_the_filter_is_there(tmp_path, monkeypatch):
    """Command construction only - this Mac's ffmpeg cannot run it."""
    captured = {}
    monkeypatch.setattr(static_gen, "drawtext_available", lambda: True)
    monkeypatch.setattr(static_gen, "_run", lambda cmd: captured.setdefault("cmd", cmd))
    generate_logo(tmp_path / "logo.mp4", text="TANGBOX")
    filters = " ".join(captured["cmd"])
    assert "drawtext" in filters
    assert "TANGBOX" in filters


def test_the_bundled_font_is_passed_to_drawtext(tmp_path, monkeypatch):
    captured = {}
    monkeypatch.setattr(static_gen, "drawtext_available", lambda: True)
    monkeypatch.setattr(static_gen, "_run", lambda cmd: captured.setdefault("cmd", cmd))
    generate_logo(tmp_path / "logo.mp4")
    assert "VT323-Regular.ttf" in " ".join(captured["cmd"])


def test_generate_all_creates_a_logo(tmp_path):
    generate_all(tmp_path)
    assert (tmp_path / LOGO_FILENAME).is_file()


def test_force_must_not_destroy_real_artwork(tmp_path):
    """Every other asset here is synthetic and disposable. This one is not.

    Once Brian drops his own logo.mp4 in, `--force` regenerating it would throw
    away artwork that exists nowhere else on the Pi.
    """
    logo = tmp_path / LOGO_FILENAME
    logo.write_bytes(b"pretend this is Brian's artwork")
    generate_all(tmp_path, force=True)
    assert logo.read_bytes() == b"pretend this is Brian's artwork"


# -- the CRT power-on zap ----------------------------------------------------


def test_the_zap_actually_animates(tmp_path):
    """A clip that renders but never changes would pass a "file exists" test.

    Decode it and check the brightness really does rise then fall: dark at the
    start (a thin line on black), bright in the middle (full frame), dark at the
    end (settled, so the ident can fade up behind it).
    """
    import subprocess

    from nostalgiabox.static_gen import generate_power_on

    out = generate_power_on(tmp_path / "power_on.mp4")
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(out),
         "-f", "rawvideo", "-pix_fmt", "gray", "-s", "32x18", "-"],
        capture_output=True, check=True,
    ).stdout
    per_frame = 32 * 18
    frames = [raw[i:i + per_frame] for i in range(0, len(raw), per_frame)]
    assert len(frames) > 10, "suspiciously few frames"
    means = [sum(f) / len(f) for f in frames]

    assert means[0] < 40, f"should start nearly black, got {means[0]:.0f}"
    assert max(means) > 180, f"should reach near-white, got {max(means):.0f}"
    assert means[-1] < 60, f"should settle dark, got {means[-1]:.0f}"
    assert means.index(max(means)) > 0, "brightest frame should not be the first"


def test_generate_all_creates_the_zap(tmp_path):
    from nostalgiabox.static_gen import POWER_ON_FILENAME

    generate_all(tmp_path)
    assert (tmp_path / POWER_ON_FILENAME).is_file()


def test_force_spares_a_replaced_zap(tmp_path):
    from nostalgiabox.static_gen import POWER_ON_FILENAME

    zap = tmp_path / POWER_ON_FILENAME
    zap.write_bytes(b"someone's own switch-on effect")
    generate_all(tmp_path, force=True)
    assert zap.read_bytes() == b"someone's own switch-on effect"


# -- the CRT power-off zap ---------------------------------------------------


def test_the_power_off_zap_collapses(tmp_path):
    """The reverse of switching on: the picture collapses to a line, the line
    to a dot, the dot winks out. Brightness must therefore START high.
    """
    import subprocess

    from nostalgiabox.static_gen import generate_power_off

    out = generate_power_off(tmp_path / "power_off.mp4")
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(out),
         "-f", "rawvideo", "-pix_fmt", "gray", "-s", "32x18", "-"],
        capture_output=True, check=True,
    ).stdout
    per_frame = 32 * 18
    frames = [raw[i:i + per_frame] for i in range(0, len(raw), per_frame)]
    means = [sum(f) / len(f) for f in frames]

    assert len(frames) > 10
    assert means[0] > 150, f"should start bright, got {means[0]:.0f}"
    assert means[-1] < 20, f"should end black, got {means[-1]:.0f}"
    assert means[0] > means[len(means) // 2] > means[-1], "should fall throughout"


def test_the_two_zaps_are_mirror_images(tmp_path):
    """On starts dark and ends dark; off starts bright and ends dark."""
    import subprocess

    from nostalgiabox.static_gen import generate_power_off, generate_power_on

    def first_mean(path):
        raw = subprocess.run(
            ["ffmpeg", "-v", "error", "-i", str(path),
             "-f", "rawvideo", "-pix_fmt", "gray", "-s", "32x18", "-vframes", "1", "-"],
            capture_output=True, check=True,
        ).stdout
        return sum(raw) / len(raw)

    on = generate_power_on(tmp_path / "on.mp4")
    off = generate_power_off(tmp_path / "off.mp4")
    assert first_mean(on) < 40
    assert first_mean(off) > 150


def test_generate_all_creates_the_power_off(tmp_path):
    from nostalgiabox.static_gen import POWER_OFF_FILENAME

    generate_all(tmp_path)
    assert (tmp_path / POWER_OFF_FILENAME).is_file()


# -- radial zaps, at output resolution ---------------------------------------
#
# Reworked 2026-08-19 on Brian's note. Two changes:
#   * RADIAL rather than a collapsing horizontal line. The line is the authentic
#     1990s CRT collapse, but he wants the quicker radial pop other sets do.
#   * 1920x1080, matching the display mode mpv now sets. At 1280x720 these were
#     being scaled up 1.5x, and a hard-edged white shape is the worst possible
#     content for that.


def frames_of(path, w=32, h=18):
    import subprocess
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(path),
         "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{w}x{h}", "-"],
        capture_output=True, check=True,
    ).stdout
    n = w * h
    return [raw[i:i+n] for i in range(0, len(raw), n)]


def lit_box(frame, w=32, h=18, thresh=110):
    xs = [i % w for i, v in enumerate(frame) if v > thresh]
    ys = [i // w for i, v in enumerate(frame) if v > thresh]
    if not xs:
        return None
    return min(xs), max(xs), min(ys), max(ys)


def test_the_power_on_zap_is_radial_not_a_line(tmp_path):
    """A growing circle is roughly as tall as it is wide; a line is not.

    The old effect opened a full-width horizontal bar first, so early frames
    were ~40:1. This asserts the shape, not just the brightness.
    """
    from nostalgiabox.static_gen import generate_power_on

    out = generate_power_on(tmp_path / "on.mp4", width=640, height=360)
    frames = frames_of(out)
    mids = [f for f in frames if lit_box(f)]
    assert len(mids) > 5, "nothing lit in any frame"
    # Take a frame partway through the growth, before it fills the screen.
    growing = [f for f in mids if (lambda b: b and (b[1]-b[0]) < 28)(lit_box(f))]
    assert growing, "the lit area never appeared partially grown"
    x0, x1, y0, y1 = lit_box(growing[len(growing)//2])
    wide, tall = (x1-x0+1), (y1-y0+1)
    # 32x18 sampling of a 16:9 frame: a circle is ~1.78x wider in cells than tall.
    ratio = (wide / 1.78) / max(tall, 1)
    assert 0.55 < ratio < 1.9, f"not circular: {wide} wide x {tall} tall (ratio {ratio:.2f})"


def test_the_power_off_zap_is_radial_too(tmp_path):
    from nostalgiabox.static_gen import generate_power_off

    out = generate_power_off(tmp_path / "off.mp4", width=640, height=360)
    frames = frames_of(out)
    shrinking = [f for f in frames if (lambda b: b and 2 < (b[1]-b[0]) < 28)(lit_box(f))]
    assert shrinking, "never caught it partly collapsed"
    x0, x1, y0, y1 = lit_box(shrinking[len(shrinking)//2])
    wide, tall = (x1-x0+1), (y1-y0+1)
    ratio = (wide / 1.78) / max(tall, 1)
    assert 0.55 < ratio < 1.9, f"not circular: {wide}x{tall} (ratio {ratio:.2f})"


def test_the_zaps_default_to_the_output_resolution(tmp_path):
    """1920x1080 - what mpv now drives - so nothing is scaled up."""
    import inspect
    from nostalgiabox.static_gen import generate_power_off, generate_power_on

    for fn in (generate_power_on, generate_power_off):
        sig = inspect.signature(fn)
        assert sig.parameters["width"].default == 1920, fn.__name__
        assert sig.parameters["height"].default == 1080, fn.__name__


# -- the ident uses the real logo --------------------------------------------


def test_the_ident_uses_logo_png_when_present(tmp_path):
    """Brian's wordmark replaces the green TANGBOX placeholder.

    Checked by looking at the pixels: the placeholder is phosphor green, the
    real thing is white with an orange circle in it.
    """
    import shutil, subprocess

    from nostalgiabox.static_gen import LOGO_IMAGE_FILENAME, DEFAULT_ASSETS_DIR, generate_logo

    src = DEFAULT_ASSETS_DIR / LOGO_IMAGE_FILENAME
    assert src.is_file(), "the bundled logo.png is missing"
    shutil.copy(src, tmp_path / LOGO_IMAGE_FILENAME)

    out = generate_logo(tmp_path / "logo.mp4", width=640, height=360)
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", "1.0", "-i", str(out),
         "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "64x36", "-"],
        capture_output=True, check=True,
    ).stdout
    px = [(raw[i], raw[i+1], raw[i+2]) for i in range(0, len(raw), 3)]
    whites = [p for p in px if min(p) > 170]
    oranges = [p for p in px if p[0] > 150 and 60 < p[1] < 170 and p[2] < 90]
    assert whites, "no white lettering - did it fall back to the placeholder?"
    assert oranges, "no orange - the fruit is missing"


def test_the_ident_still_works_without_the_png(tmp_path):
    """A missing logo must never mean a black screen at power-on."""
    from nostalgiabox.static_gen import generate_logo

    out = generate_logo(tmp_path / "logo.mp4", width=640, height=360)
    assert out.is_file() and out.stat().st_size > 1000


def test_the_ident_defaults_to_output_resolution():
    import inspect

    from nostalgiabox.static_gen import generate_logo

    sig = inspect.signature(generate_logo)
    assert sig.parameters["width"].default == 1920
    assert sig.parameters["height"].default == 1080


# -- smoothness --------------------------------------------------------------
#
# Brian: "both zaps are a bit too quick and lightly stuttering ... looking for a
# smooth zap motion". The display is 60Hz and the clips are 60fps, so this is
# not a rate mismatch - it is distance-per-frame. Covering the whole screen in
# 0.55s means each early frame jumps a long way, which reads as stepping no
# matter what the frame rate is.


def test_the_zap_starts_on_black_so_the_load_hitch_is_hidden(tmp_path):
    """mpv takes a moment to open a file. Let that land on black, not mid-motion."""
    from nostalgiabox.static_gen import generate_power_on

    out = generate_power_on(tmp_path / "on.mp4", width=640, height=360)
    frames = frames_of(out)
    lead = [f for f in frames[:4]]
    assert all(sum(f) / len(f) < 6 for f in lead), "the first frames are not black"


def test_no_frame_jumps_a_long_way(tmp_path):
    """The actual measure of smoothness: bounded movement between frames."""
    from nostalgiabox.static_gen import generate_power_on

    out = generate_power_on(tmp_path / "on.mp4", width=640, height=360)
    widths = []
    for f in frames_of(out):
        b = lit_box(f)
        widths.append(0 if not b else b[1] - b[0] + 1)
    growing = [w for w in widths if w > 0]
    jumps = [abs(b - a) for a, b in zip(growing, growing[1:])]
    # 32 cells across. Tightened from 8 once 0.95s proved smooth on the TV, so
    # speeding the zaps back up cannot quietly undo that.
    assert max(jumps) <= 5, f"biggest single-frame jump was {max(jumps)} of 32 cells"


def test_the_off_zap_vanishes_rather_than_fading_a_dot(tmp_path):
    """Brian: "make the off zap completely disappear at the center".

    It should end by shrinking to NOTHING, not by holding a dot and dimming it.
    So the final frames must have no lit pixels at all - not merely dark ones.
    """
    from nostalgiabox.static_gen import generate_power_off

    out = generate_power_off(tmp_path / "off.mp4", width=640, height=360)
    frames = frames_of(out)
    assert lit_box(frames[-1], thresh=40) is None, "something is still lit at the end"
    assert lit_box(frames[-2], thresh=40) is None, "still lit one frame from the end"
    # And it must genuinely shrink on the way, not just cut out.
    widths = [0 if not lit_box(f) else lit_box(f)[1] - lit_box(f)[0] + 1 for f in frames]
    lit = [w for w in widths if w > 0]
    assert lit[0] > 20 and min(lit) <= 3, f"did not close down: {lit[:3]} ... {lit[-3:]}"


def test_the_off_zap_lingers_near_the_centre(tmp_path):
    """Reaching zero is not enough - it has to be SEEN converging.

    The first attempt closed to nothing but spent only 3 frames (50ms) at small
    sizes, and its last visible state was still ~6% of the screen wide before it
    cut out. Brian's report was "I don't see the zap reaching the center", which
    a "does it end black" test happily passed.
    """
    from nostalgiabox.static_gen import generate_power_off

    out = generate_power_off(tmp_path / "off.mp4", width=1280, height=720)
    widths = []
    for f in frames_of(out, w=128, h=72):
        b = lit_box(f, w=128, h=72, thresh=40)
        widths.append(0 if not b else b[1] - b[0] + 1)
    lit = [w for w in widths if w > 0]
    small = [w for w in lit if w <= 20]
    assert len(small) >= 7, f"only {len(small)} frames spent near the centre"
    assert min(lit) <= 3, f"smallest it ever gets is {min(lit)} of 128 - not a point"


# -- the animated ident ------------------------------------------------------
#
# Brian designed an animation and asked for the shimmer removed and the length
# cut to 5s. Rather than trying to strip a baked-in effect out of finished
# video, it is rebuilt from his vector artwork: flat brand colours, no effects
# by construction, and the timing lives in code where it can be tuned.
#
# The motion, measured from his original: the orange sits alone dead centre at
# constant size, then the WORDMARK scales up around it while the orange slides
# right into place as the letter o.


def test_the_ident_animates_when_the_layers_are_present(tmp_path):
    import shutil
    import subprocess

    from nostalgiabox.static_gen import (
        DEFAULT_ASSETS_DIR,
        LOGO_GLYPH_PREFIX,
        LOGO_LAYER_CIRCLE,
        LOGO_LAYER_LEAVES,
        generate_logo,
    )

    layers = sorted(DEFAULT_ASSETS_DIR.glob(f"{LOGO_GLYPH_PREFIX}*.png"))
    assert layers, "bundled glyph layers are missing"
    for src in layers + [DEFAULT_ASSETS_DIR / LOGO_LAYER_CIRCLE,
                         DEFAULT_ASSETS_DIR / LOGO_LAYER_LEAVES]:
        assert src.is_file(), f"bundled {src.name} is missing"
        shutil.copy(src, tmp_path / src.name)

    out = generate_logo(tmp_path / "logo.mp4", width=640, height=360, duration=5.0)

    def sample(at):
        raw = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", str(at), "-i", str(out), "-frames:v", "1",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "64x36", "-"],
            capture_output=True, check=True,
        ).stdout
        px = [(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, len(raw), 3)]
        whites = sum(1 for p in px if min(p) > 170)
        oranges = sum(1 for p in px if p[0] > 150 and 60 < p[1] < 170 and p[2] < 90)
        return whites, oranges

    early_w, early_o = sample(0.2)
    late_w, late_o = sample(4.5)

    assert early_o > 0, "no orange at the start - it should open on the fruit alone"
    assert early_w == 0, f"lettering visible at 0.2s ({early_w} px) - it should not be"
    assert late_w > 0, "no lettering at the end"
    assert late_o > 0, "the orange vanished"


def test_the_ident_is_silent(tmp_path):
    """Brian: "no sound, keep animation mute." It plays at every power-on."""
    import shutil
    import subprocess

    from nostalgiabox.static_gen import (
        DEFAULT_ASSETS_DIR, LOGO_GLYPH_PREFIX, LOGO_LAYER_CIRCLE, LOGO_LAYER_LEAVES, generate_logo,
    )

    for src in sorted(DEFAULT_ASSETS_DIR.glob(f"{LOGO_GLYPH_PREFIX}*.png")) + [
        DEFAULT_ASSETS_DIR / LOGO_LAYER_CIRCLE, DEFAULT_ASSETS_DIR / LOGO_LAYER_LEAVES
    ]:
        shutil.copy(src, tmp_path / src.name)
    out = generate_logo(tmp_path / "logo.mp4", width=640, height=360, duration=5.0)
    streams = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type",
         "-of", "csv=p=0", str(out)],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    assert "audio" not in streams, f"the ident has audio: {streams}"


def test_the_ident_defaults_to_five_seconds():
    """Brian: "5 seconds is fine to teach kids to wait"."""
    import inspect

    from nostalgiabox.static_gen import generate_logo

    assert inspect.signature(generate_logo).parameters["duration"].default == 5.0



def test_the_letters_never_scale_or_fade(tmp_path):
    """Brian: "the letters should smoothly slide out from behind the orange and
    not scale up in size or fade in."

    Checked structurally, on the generated ffmpeg command: no per-letter alpha
    ramp, and each letter's only time-varying property is its x position. A
    pixel test could not distinguish "grew into place" from "slid into place"
    at the moment it arrives.
    """
    from nostalgiabox.static_gen import (
        DEFAULT_ASSETS_DIR, LOGO_GLYPH_PREFIX, LOGO_LAYER_CIRCLE,
        LOGO_LAYER_LEAVES, _ident_command,
    )

    glyphs = sorted(DEFAULT_ASSETS_DIR.glob(f"{LOGO_GLYPH_PREFIX}*.png"))
    cmd = _ident_command(
        tmp_path / "out.mp4", glyphs,
        DEFAULT_ASSETS_DIR / LOGO_LAYER_CIRCLE,
        DEFAULT_ASSETS_DIR / LOGO_LAYER_LEAVES,
        width=1920, height=1080, fps=60, duration=5.0,
    )
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "colorchannelmixer" not in graph, "something is fading"
    # Every scale= must be to a fixed size, never an expression in t.
    for seg in graph.split(";"):
        if seg.strip().startswith("[") and "scale=" in seg:
            scale_arg = seg.split("scale=")[1].split("[")[0]
            assert "t" not in scale_arg.replace("scale", ""), f"scale varies: {seg}"
    # y must be constant; only x moves.
    for seg in graph.split(";"):
        if "overlay=" in seg:
            y_arg = seg.split(":y=")[1].split(":")[0].split("[")[0]
            assert y_arg.strip().lstrip("-").isdigit(), f"y is not constant: {y_arg}"


def test_the_easing_overshoots_and_settles(tmp_path):
    """Brian asked for momentum - "maybe even a rubberband bounce back to form".

    Measured, not asserted structurally: the leftmost letter should travel PAST
    its final position and come back, so the extreme is not the resting place.
    """
    import subprocess

    from nostalgiabox.static_gen import (
        DEFAULT_ASSETS_DIR, LOGO_GLYPH_PREFIX, LOGO_LAYER_CIRCLE,
        LOGO_LAYER_LEAVES, _ident_command,
    )

    glyphs = sorted(DEFAULT_ASSETS_DIR.glob(f"{LOGO_GLYPH_PREFIX}*.png"))
    out = tmp_path / "o.mp4"
    subprocess.run(_ident_command(
        out, glyphs, DEFAULT_ASSETS_DIR / LOGO_LAYER_CIRCLE,
        DEFAULT_ASSETS_DIR / LOGO_LAYER_LEAVES,
        width=960, height=540, fps=60, duration=5.0,
    ), check=True)
    raw = subprocess.run(
        ["ffmpeg", "-v", "error", "-i", str(out), "-f", "rawvideo",
         "-pix_fmt", "gray", "-s", "96x54", "-"],
        capture_output=True, check=True,
    ).stdout
    n = 96 * 54
    lefts = []
    for i in range(0, len(raw), n):
        f = raw[i:i + n]
        xs = [j % 96 for j, v in enumerate(f) if v > 90]
        if xs:
            lefts.append(min(xs))
    settled = lefts[-1]
    furthest = min(lefts)
    assert furthest < settled, (
        f"no overshoot: furthest left {furthest}, settled at {settled}"
    )
