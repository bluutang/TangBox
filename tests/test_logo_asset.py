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
