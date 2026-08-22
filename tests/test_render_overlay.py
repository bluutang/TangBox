"""Guards on scripts/render-overlay.py.

The script exists because most of what the box draws is ASS, and libass runs
perfectly well on a Mac - so "you cannot see it without a television" was only
ever true of the CRT shader. Its value is being able to LOOK at an overlay
before it ships, which is how the timeline's layout bug was caught after 499
tests had passed on it.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "render-overlay.py"


def _module():
    spec = importlib.util.spec_from_file_location("render_overlay", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_script_exists():
    assert SCRIPT.is_file()


def test_the_document_declares_the_canvas_the_box_draws_on():
    doc = _module().ass_document(["{\\an9}hello"])
    # libass positions everything against these; get them wrong and every
    # co-ordinate in overlay.py lands somewhere else.
    assert "PlayResX: 1280" in doc
    assert "PlayResY: 720" in doc


def test_every_line_becomes_its_own_dialogue_event():
    doc = _module().ass_document(["one", "two", "three"])
    assert doc.count("Dialogue:") == 3


def test_blank_lines_are_not_drawn():
    doc = _module().ass_document(["one", "", "two"])
    assert doc.count("Dialogue:") == 2


def test_the_overlays_it_can_draw_are_all_real():
    mod = _module()
    for name in mod.OVERLAYS:
        assert callable(mod.OVERLAYS[name])
