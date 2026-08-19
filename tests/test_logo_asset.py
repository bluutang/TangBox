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
