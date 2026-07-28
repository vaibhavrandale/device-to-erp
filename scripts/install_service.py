#!/usr/bin/env python3
"""Install systemd service so reboot = git pull + run attendance."""

from __future__ import annotations

import getpass
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVICE_NAME = "taypro-fingerprint.service"
SERVICE_PATH = Path("/etc/systemd/system") / SERVICE_NAME


def main() -> int:
    user = getpass.getuser()
    boot = ROOT / "scripts" / "boot_run.py"
    if not boot.exists():
        print("missing scripts/boot_run.py")
        return 1

    unit = f"""[Unit]
Description=Taypro fingerprint attendance (git pull + run on boot)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User={user}
WorkingDirectory={ROOT}
ExecStart=/usr/bin/python3 {boot}
Restart=always
RestartSec=8
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"""

    print(unit)
    print(f"\nWriting {SERVICE_PATH} (needs sudo)...")
    tmp = Path("/tmp") / SERVICE_NAME
    tmp.write_text(unit, encoding="utf-8")
    cmds = [
        ["sudo", "cp", str(tmp), str(SERVICE_PATH)],
        ["sudo", "systemctl", "daemon-reload"],
        ["sudo", "systemctl", "enable", SERVICE_NAME],
        ["sudo", "systemctl", "restart", SERVICE_NAME],
    ]
    for cmd in cmds:
        print("$", " ".join(cmd))
        subprocess.run(cmd, check=False)

    print("\nDone. After each laptop git push, on Pi just:")
    print("  sudo reboot")
    print("Logs:")
    print(f"  journalctl -u {SERVICE_NAME} -f")
    print(f"  tail -f {ROOT}/data/boot_run.log")
    return 0


if __name__ == "__main__":
    if os.geteuid() == 0:
        print("Run as normal user (taypro), not root — script will sudo when needed.")
    raise SystemExit(main())
