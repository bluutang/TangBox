"""Guards on scripts/install.sh.

The rebrand renamed the user-facing command to `tangbox` but deliberately kept
the Python package as `nostalgiabox`, so upstream fixes still merge. Anything in
a shell script that names a path had to be checked by hand, and one wasn't.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"

# Matches the repo-relative part of e.g. "${REPO_DIR}/tangbox/assets/fonts/*.ttf"
_ASSET_PATH_RE = re.compile(r"\$\{REPO_DIR\}[\"']?/([A-Za-z0-9_./-]+)")


def test_install_script_exists():
    assert INSTALL_SH.is_file()


def test_paths_the_installer_references_actually_exist():
    """Every ${REPO_DIR}-relative path in install.sh must resolve.

    The font-install block globbed `tangbox/assets/fonts/*.ttf`, a folder that
    has never existed - the fonts live under `nostalgiabox/`. `compgen -G` finds
    nothing, the `if` is skipped, and the whole block does nothing SILENTLY. No
    error, no warning, and the installer still prints "==> Done!".
    """
    text = INSTALL_SH.read_text()
    missing = []
    for rel in _ASSET_PATH_RE.findall(text):
        rel = rel.rstrip("/")
        # Strip a trailing glob segment: fonts/*.ttf -> fonts
        parts = [p for p in rel.split("/") if "*" not in p]
        if not parts:
            continue
        candidate = REPO_ROOT / "/".join(parts)
        # .venv and config.yaml are created BY the installer, so their absence
        # in a fresh checkout is correct rather than a bug.
        if candidate.name in {".venv", "config.yaml"} or ".venv" in candidate.parts:
            continue
        if not candidate.exists():
            missing.append(rel)
    assert not missing, f"install.sh references paths that do not exist: {missing}"


def test_the_bundled_font_is_where_the_installer_looks_for_it():
    """The folder install.sh globs for *.ttf must actually contain one."""
    text = INSTALL_SH.read_text()
    font_dirs = {
        rel.rstrip("/")
        for rel in _ASSET_PATH_RE.findall(text)
        if "assets/fonts" in rel
    }
    assert font_dirs, "install.sh no longer installs the OSD font at all"
    for rel in font_dirs:
        ttfs = list((REPO_ROOT / rel).glob("*.ttf"))
        assert ttfs, f"install.sh globs {rel}/*.ttf but no .ttf is there"
