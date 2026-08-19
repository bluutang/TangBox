"""Tests for scripts/display-mode.sh.

The Pi came up driving the TV at 3840x2160@30 - 4K, thirty hertz. For a box
showing 480-line cartoons that is the worst of both worlds: no extra detail to
be had from the source, half the refresh rate of 1080p60, and the 1280x720
overlay canvas stretched 3x instead of 1.5x, which is why the HUD text never
got truly crisp no matter what was done to the blur or the weight.

Same file as quiet-boot.sh edits, so the same brutal rule applies: cmdline.txt
must be EXACTLY ONE LINE or the Pi will not boot.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "display-mode.sh"

REAL_CMDLINE = (
    "console=serial0,115200 console=tty3 root=PARTUUID=7cc30427-02 "
    "rootfstype=ext4 fsck.repair=yes rootwait "
    "ds=nocloud;i=rpi-imager-1787023251516 quiet loglevel=0\n"
)

DEFAULT_MODE = "video=HDMI-A-1:1920x1080@60"


@pytest.fixture
def boot(tmp_path: Path) -> Path:
    d = tmp_path / "firmware"
    d.mkdir()
    (d / "cmdline.txt").write_text(REAL_CMDLINE)
    return d


def run(boot_dir: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        env={"PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "BOOT_DIR": str(boot_dir)},
        capture_output=True,
        text=True,
    )


def test_script_exists():
    assert SCRIPT.is_file()


def test_it_forces_1080p60_by_default(boot: Path):
    assert run(boot).returncode == 0
    assert DEFAULT_MODE in (boot / "cmdline.txt").read_text()


def test_result_is_exactly_one_line(boot: Path):
    run(boot)
    text = (boot / "cmdline.txt").read_text()
    assert text.rstrip("\n").count("\n") == 0


def test_existing_boot_options_survive(boot: Path):
    run(boot)
    text = (boot / "cmdline.txt").read_text()
    for original in ("root=PARTUUID=7cc30427-02", "rootwait", "console=tty3", "quiet"):
        assert original in text


def test_semicolons_survive(boot: Path):
    run(boot)
    assert "ds=nocloud;i=rpi-imager-1787023251516" in (boot / "cmdline.txt").read_text()


def test_running_twice_does_not_stack_modes(boot: Path):
    run(boot)
    run(boot)
    assert (boot / "cmdline.txt").read_text().count("video=HDMI") == 1


def test_a_different_mode_replaces_the_old_one(boot: Path):
    """Changing your mind must not leave two video= parameters fighting."""
    run(boot)
    run(boot, "1280x720@60")
    text = (boot / "cmdline.txt").read_text()
    assert text.count("video=HDMI") == 1
    assert "1280x720@60" in text
    assert "1920x1080@60" not in text


def test_a_custom_mode_is_accepted(boot: Path):
    run(boot, "1920x1080@50")
    assert "video=HDMI-A-1:1920x1080@50" in (boot / "cmdline.txt").read_text()


def test_a_nonsense_mode_is_refused(boot: Path):
    """Better to reject it than to write something the kernel silently ignores."""
    result = run(boot, "enormous")
    assert result.returncode != 0
    assert (boot / "cmdline.txt").read_text() == REAL_CMDLINE


def test_it_backs_up_before_touching_anything(boot: Path):
    run(boot)
    backup = boot / "cmdline.txt.tangbox-display-backup"
    assert backup.is_file()
    assert backup.read_text() == REAL_CMDLINE


def test_undo_restores_the_original_exactly(boot: Path):
    run(boot)
    assert run(boot, "--undo").returncode == 0
    assert (boot / "cmdline.txt").read_text() == REAL_CMDLINE


def test_undo_without_a_backup_is_an_error(boot: Path):
    assert run(boot, "--undo").returncode != 0


def test_status_changes_nothing(boot: Path):
    assert run(boot, "--status").returncode == 0
    assert (boot / "cmdline.txt").read_text() == REAL_CMDLINE


def test_missing_cmdline_is_an_error(tmp_path: Path):
    empty = tmp_path / "nothing"
    empty.mkdir()
    result = run(empty)
    assert result.returncode != 0
    assert "cmdline.txt" in (result.stderr + result.stdout)
