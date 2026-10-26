#!/usr/bin/env python3
"""TangBox Voice Assistant Bridge for Google Home (via Sinric Pro).

Listens for voice commands from Google Home / Assistant ("turn on TangBox",
"turn off TangBox") via Sinric Pro and toggles TangBox between awake and
standby mode by sending SIGUSR1 to the tangbox process.

Also reports real-time power state back to Google Home if TangBox is turned
on/off using the physical IR remote control.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
from typing import Optional

from sinricpro import SinricPro, SinricProConfig, SinricProSwitch
from sinricpro.utils.logger import SinricProLogger, LogLevel

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("tangbox-voice")

ENV_FILE = Path.home() / ".tangbox-voice.env"
STANDBY_FLAG = Path("/tmp/tangbox-standby")


def load_env() -> dict[str, str]:
    if not ENV_FILE.exists():
        log.error("Missing config file: %s", ENV_FILE)
        sys.exit(1)
    env = {}
    for line in ENV_FILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip("\"'")
    return env


def get_tangbox_pid() -> Optional[int]:
    try:
        out = subprocess.check_output(
            ["pgrep", "-f", "/home/brian/TangBox/.venv/bin/tangbox"],
            text=True,
        ).strip()
        if out:
            return int(out.splitlines()[0])
    except Exception:
        pass
    return None


def is_tangbox_in_standby(pid: Optional[int]) -> bool:
    if pid is None:
        return True

    # 1. Direct query via mpv IPC socket if available (authoritative)
    sock_path = Path("/tmp/mpv.sock")
    if sock_path.exists():
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as s:
                s.settimeout(0.5)
                s.connect(str(sock_path))
                s.sendall(b'{"command": ["get_property", "idle-active"]}\n')
                res = json.loads(s.recv(1024).decode())
                if res.get("error") == "success":
                    is_idle = bool(res.get("data", False))
                    return is_idle
        except Exception:
            pass

    if STANDBY_FLAG.exists():
        return True

    # 2. Fallback: inspect open media file descriptors of tangbox process
    try:
        fd_dir = Path(f"/proc/{pid}/fd")
        if fd_dir.exists():
            for fd in fd_dir.iterdir():
                try:
                    target = str(fd.readlink())
                    if any(
                        target.endswith(ext)
                        for ext in (
                            ".mp4",
                            ".mkv",
                            ".avi",
                            ".webm",
                            ".m4v",
                            ".mov",
                            ".ts",
                        )
                    ):
                        return False
                except (OSError, FileNotFoundError):
                    continue
    except Exception:
        pass
    return True


def set_indicator(is_on: bool) -> None:
    try:
        script = Path("/home/brian/TangBox/scripts/set-led-state.sh")
        if script.exists():
            subprocess.run([str(script), "on" if is_on else "standby"], check=False)
    except Exception as e:
        log.debug("Failed to set indicator: %s", e)


class VoiceBridge:
    def __init__(self, device_id: str, app_key: str, app_secret: str) -> None:
        self.device_id = device_id
        self.app_key = app_key
        self.app_secret = app_secret
        self.device = SinricProSwitch(device_id)
        self.sinric: Optional[SinricPro] = None
        self.last_reported_state: Optional[bool] = None

    async def on_power_state(self, state: bool) -> bool:
        pid = get_tangbox_pid()
        if pid is None:
            log.warning("TangBox main process is not running!")
            return False

        in_standby = is_tangbox_in_standby(pid)
        log.info(
            "Voice command received: state=%s (in_standby=%s, pid=%s)",
            state,
            in_standby,
            pid,
        )

        # state == True means user asked to Turn ON TangBox
        if state and in_standby:
            log.info("Waking TangBox from standby via SIGUSR1 (PID %s)", pid)
            STANDBY_FLAG.unlink(missing_ok=True)
            set_indicator(True)
            os.kill(pid, signal.SIGUSR1)
            self.last_reported_state = True
        elif not state and not in_standby:
            log.info("Switching TangBox to standby via SIGUSR1 (PID %s)", pid)
            STANDBY_FLAG.touch()
            set_indicator(False)
            os.kill(pid, signal.SIGUSR1)
            self.last_reported_state = False
        else:
            log.info("TangBox is already in requested state (ON=%s)", state)

        return True

    async def sync_loop(self) -> None:
        """Keep Google Home updated if state is changed via physical remote."""
        # Wait until connected
        connect_wait = 0
        while not (self.sinric and self.sinric.is_connected()):
            await asyncio.sleep(2)
            connect_wait += 2
            if connect_wait >= 30:
                log.warning(
                    "Not connected to Sinric Pro after 30s. Exiting for systemd restart..."
                )
                sys.exit(1)

        # Initial state sync
        pid = get_tangbox_pid()
        is_on = not is_tangbox_in_standby(pid)
        self.last_reported_state = is_on
        set_indicator(is_on)
        log.info(
            "Initial TangBox state synced to Google Home: %s",
            "ON" if is_on else "OFF",
        )
        try:
            await self.device.send_power_state_event(
                is_on, cause="PHYSICAL_INTERACTION"
            )
        except Exception as e:
            log.debug("Could not send initial state event: %s", e)

        disconnected_count = 0
        while True:
            await asyncio.sleep(3)
            try:
                if self.sinric and not self.sinric.is_connected():
                    disconnected_count += 1
                    if disconnected_count >= 10:  # 30 seconds disconnected
                        log.warning(
                            "Sinric Pro WebSocket dropped for >30s. Exiting for systemd restart..."
                        )
                        sys.exit(1)
                else:
                    disconnected_count = 0

                pid = get_tangbox_pid()
                current_on = not is_tangbox_in_standby(pid)
                if (
                    current_on != self.last_reported_state
                    and self.sinric
                    and self.sinric.is_connected()
                ):
                    log.info(
                        "State change detected (remote/ssh). Updating Google Home to: %s",
                        "ON" if current_on else "OFF",
                    )
                    self.last_reported_state = current_on
                    if current_on:
                        STANDBY_FLAG.unlink(missing_ok=True)
                    else:
                        STANDBY_FLAG.touch()
                    set_indicator(current_on)
                    await self.device.send_power_state_event(
                        current_on, cause="PHYSICAL_INTERACTION"
                    )
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.debug("Error in sync loop: %s", e)

    async def start(self) -> None:
        self.device.on_power_state(self.on_power_state)
        self.sinric = SinricPro.get_instance()
        self.sinric.add(self.device)

        config = SinricProConfig(
            app_key=self.app_key,
            app_secret=self.app_secret,
            debug=True,
        )
        await self.sinric.begin(config)
        log.info("Sinric Pro voice bridge active for device: %s", self.device_id)

        sync_task = asyncio.create_task(self.sync_loop())
        try:
            while True:
                await asyncio.sleep(3600)
        finally:
            sync_task.cancel()
            await self.sinric.stop()


def main() -> None:
    env = load_env()
    app_key = env.get("SINRIC_APP_KEY", "")
    app_secret = env.get("SINRIC_APP_SECRET", "")
    device_id = env.get("SINRIC_DEVICE_ID", "")

    if not app_key or not app_secret or not device_id:
        log.error("Missing required keys in %s", ENV_FILE)
        sys.exit(1)

    bridge = VoiceBridge(device_id, app_key, app_secret)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def handle_signal(*_):
        log.info("Stopping voice daemon...")
        for task in asyncio.all_tasks(loop):
            task.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    try:
        loop.run_until_complete(bridge.start())
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        loop.close()
        log.info("Voice daemon shutdown cleanly.")


if __name__ == "__main__":
    main()
