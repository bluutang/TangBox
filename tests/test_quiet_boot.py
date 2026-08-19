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

QUIET_FLAGS = [
    "quiet",
    "loglevel=0",
    "logo.nologo",
    "vt.global_cursor_default=0",
    "systemd.show_status=false",
]


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


def test_it_silences_systemd_not_just_the_kernel(boot: Path):
    """`quiet` covers the KERNEL. Most boot text is systemd's own status output.

    Brian watched the first quiet boot and still saw terminal lines - these were
    "[ OK ] Started ..." from systemd, which quiet and loglevel do nothing about.
    """
    run(boot)
    assert "systemd.show_status=false" in (boot / "cmdline.txt").read_text()


def test_a_cmdline_with_no_trailing_newline_is_handled(tmp_path: Path):
    """The real Pi's file has none - Imager writes it without one."""
    d = tmp_path / "firmware"
    d.mkdir()
    (d / "cmdline.txt").write_text(REAL_CMDLINE.rstrip("\n"))
    (d / "config.txt").write_text(REAL_CONFIG)
    assert run(d).returncode == 0
    text = (d / "cmdline.txt").read_text()
    assert text.rstrip("\n").count("\n") == 0
    assert "quiet" in text


def test_semicolons_in_parameters_survive(tmp_path: Path):
    """The real Pi carries ds=nocloud;i=rpi-imager-... - a semicolon mid-line."""
    d = tmp_path / "firmware"
    d.mkdir()
    (d / "cmdline.txt").write_text(
        "root=PARTUUID=7cc30427-02 ds=nocloud;i=rpi-imager-1787023251516 rootwait\n"
    )
    (d / "config.txt").write_text(REAL_CONFIG)
    run(d)
    assert "ds=nocloud;i=rpi-imager-1787023251516" in (d / "cmdline.txt").read_text()


# -- moving the console off the visible screen -------------------------------
#
# quiet/loglevel/show_status reduce how much gets WRITTEN. Anything still
# written lands on tty1, which is the screen. Pointing the console at tty3 - a
# virtual terminal nobody displays - means stray output goes somewhere
# invisible instead, and TangBox owns tty1 uncontested.
#
# This is the first thing the script MODIFIES rather than appends, so it gets
# its own tests.


def test_the_console_moves_off_the_visible_terminal(boot: Path):
    run(boot)
    text = (boot / "cmdline.txt").read_text()
    assert "console=tty3" in text
    assert "console=tty1" not in text


def test_the_serial_console_is_left_alone(boot: Path):
    """console=serial0 is how you debug a Pi that will not boot. Don't touch it."""
    run(boot)
    assert "console=serial0,115200" in (boot / "cmdline.txt").read_text()


def test_undo_puts_the_console_back(boot: Path):
    run(boot)
    run(boot, "--undo")
    assert (boot / "cmdline.txt").read_text() == REAL_CMDLINE


def test_running_twice_does_not_stack_consoles(boot: Path):
    run(boot)
    run(boot)
    assert (boot / "cmdline.txt").read_text().count("console=tty3") == 1


# -- keeping the console off the screen --------------------------------------
#
# console=tty3 is a virtual terminal nobody displays. Dropping the VT console
# ENTIRELY was tried and reverted: it stopped the shutdown flash, but with no VT
# owning the framebuffer nothing cleared it before mpv started, and boot showed
# uninitialised video memory as coloured garbage. Boot is seen every day.
#
# The text tty3 accumulates is dealt with by tangbox.service clearing it at
# startup - see test_service_clears_the_console_vt.


def test_the_serial_console_survives(boot: Path):
    """The only way to see a Pi that will not boot. Never remove it."""
    run(boot)
    assert "console=serial0,115200" in (boot / "cmdline.txt").read_text()


def test_an_already_moved_console_is_left_alone(boot_tty3: Path):
    """Re-running on a box already set up must not disturb it."""
    run(boot_tty3)
    text = (boot_tty3 / "cmdline.txt").read_text()
    assert text.count("console=tty3") == 1
    assert "console=tty1" not in text


def test_undo_brings_the_console_back(boot: Path):
    run(boot)
    run(boot, "--undo")
    assert (boot / "cmdline.txt").read_text() == REAL_CMDLINE


@pytest.fixture
def boot_tty3(tmp_path: Path) -> Path:
    d = tmp_path / "firmware"
    d.mkdir()
    (d / "cmdline.txt").write_text(
        "console=serial0,115200 console=tty3 root=PARTUUID=abc-02 rootwait\n"
    )
    (d / "config.txt").write_text(REAL_CONFIG)
    return d


def test_service_clears_the_console_vt():
    """The other half of the shutdown fix, and the half that is not in cmdline.

    Without it tty3 keeps its fsck and cloud-init lines, and systemd shows them
    for about a second at shutdown when it switches the display to that VT.
    """
    unit = (REPO_ROOT / "scripts" / "tangbox.service").read_text()
    assert "/dev/tty3" in unit, "the service no longer clears the console VT"
    assert "ExecStartPost" in unit


def test_a_console_is_added_when_none_exists(tmp_path: Path):
    """A VT console has to EXIST, not merely be out of the way.

    Something must own and clear the framebuffer before mpv starts. With no VT
    at all, boot showed uninitialised video memory as coloured garbage - which
    is how the "remove it entirely" attempt was caught. A Pi ships with
    console=tty1 so this case only arises after that attempt, but the script has
    to be able to put things right.
    """
    d = tmp_path / "firmware"
    d.mkdir()
    (d / "cmdline.txt").write_text(
        "console=serial0,115200 root=PARTUUID=abc-02 rootwait quiet\n"
    )
    (d / "config.txt").write_text(REAL_CONFIG)
    run(d)
    text = (d / "cmdline.txt").read_text()
    assert "console=tty3" in text
    assert text.count("console=tty3") == 1
    assert "console=serial0,115200" in text


def test_the_console_clear_runs_as_root():
    """/dev/tty3 is 0600 root:tty on this Pi - NOT the usual 0620.

    The service user cannot write to it, so the clear needs systemd's `+`
    prefix to run privileged. Without it the step failed silently, which looked
    exactly like it having worked.
    """
    unit = (REPO_ROOT / "scripts" / "tangbox.service").read_text()
    line = next(l for l in unit.splitlines() if l.startswith("ExecStartPost="))
    assert line.startswith("ExecStartPost=+"), f"not privileged: {line}"


def test_the_console_clear_does_not_swallow_errors():
    """The same silent-failure trap as the install.sh font glob."""
    unit = (REPO_ROOT / "scripts" / "tangbox.service").read_text()
    line = next(l for l in unit.splitlines() if l.startswith("ExecStartPost="))
    assert "2>/dev/null" not in line, "a failure here would be invisible again"
