"""Tests for scripts/quiet-boot.sh.

The Pi scrolls ~20 seconds of kernel messages before TangBox takes the screen.
Silencing that means editing /boot/firmware/cmdline.txt, and that file has one
brutal rule: it must be EXACTLY ONE LINE. A stray newline and the Pi will not
boot, and recovery means pulling the SD card and editing it on a Mac.

So the line-mangling is proven here, on a laptop, against a throwaway directory
before it ever touches the real boot partition.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "quiet-boot.sh"

# A real Raspberry Pi OS cmdline.txt, trailing newline and all.
REAL_CMDLINE = (
    "console=serial0,115200 console=tty1 root=PARTUUID=fbb1c62b-02 "
    "rootfstype=ext4 fsck.repair=yes rootwait "
    "cfg80211.ieee80211_regdom=US\n"
)

REAL_CONFIG = """[all]
dtparam=audio=on
camera_auto_detect=1
display_auto_detect=1
arm_64bit=1
"""

QUIET_FLAGS = ["quiet", "loglevel=0", "logo.nologo", "vt.global_cursor_default=0"]


@pytest.fixture
def boot(tmp_path: Path) -> Path:
    d = tmp_path / "firmware"
    d.mkdir()
    (d / "cmdline.txt").write_text(REAL_CMDLINE)
    (d / "config.txt").write_text(REAL_CONFIG)
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


def test_adds_the_quiet_flags(boot: Path):
    assert run(boot).returncode == 0
    text = (boot / "cmdline.txt").read_text()
    for flag in QUIET_FLAGS:
        assert flag in text, f"{flag} missing from {text!r}"


def test_result_is_exactly_one_line(boot: Path):
    """The rule that bricks a Pi if broken."""
    run(boot)
    text = (boot / "cmdline.txt").read_text()
    assert text.count("\n") <= 1
    assert text.rstrip("\n").count("\n") == 0


def test_existing_boot_options_are_preserved(boot: Path):
    """Never drop root= or rootfstype= - the Pi would not find its filesystem."""
    run(boot)
    text = (boot / "cmdline.txt").read_text()
    for original in ("root=PARTUUID=fbb1c62b-02", "rootfstype=ext4", "rootwait"):
        assert original in text


def test_running_twice_changes_nothing_the_second_time(boot: Path):
    run(boot)
    once = (boot / "cmdline.txt").read_text()
    run(boot)
    assert (boot / "cmdline.txt").read_text() == once
    assert once.count("quiet") == 1


def test_it_backs_up_before_touching_anything(boot: Path):
    run(boot)
    backup = boot / "cmdline.txt.tangbox-backup"
    assert backup.is_file()
    assert backup.read_text() == REAL_CMDLINE


def test_undo_restores_the_original_exactly(boot: Path):
    run(boot)
    assert run(boot, "--undo").returncode == 0
    assert (boot / "cmdline.txt").read_text() == REAL_CMDLINE
    assert (boot / "config.txt").read_text() == REAL_CONFIG


def test_disables_the_rainbow_splash(boot: Path):
    run(boot)
    assert "disable_splash=1" in (boot / "config.txt").read_text()


def test_disable_splash_is_not_added_twice(boot: Path):
    run(boot)
    run(boot)
    assert (boot / "config.txt").read_text().count("disable_splash=1") == 1


def test_missing_cmdline_is_an_error_not_a_silent_skip(tmp_path: Path):
    empty = tmp_path / "nothing"
    empty.mkdir()
    result = run(empty)
    assert result.returncode != 0
    assert "cmdline.txt" in (result.stderr + result.stdout)


def test_undo_without_a_backup_is_an_error(boot: Path):
    result = run(boot, "--undo")
    assert result.returncode != 0


def test_status_reports_without_changing_anything(boot: Path):
    result = run(boot, "--status")
    assert result.returncode == 0
    assert (boot / "cmdline.txt").read_text() == REAL_CMDLINE
