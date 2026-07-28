#!/usr/bin/env python3
"""
Boot runner for RasPi attendance.

On device restart:
  1) git fetch + pull (latest code you pushed)
  2) pip install -r requirements.txt if needed (quiet)
  3) start main.py

Install once (on Pi):
  python3 scripts/install_service.py

Then after every laptop `git push`, just reboot the Pi:
  sudo reboot
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_PYTHON = ROOT / ".venv" / "bin" / "python"
MAIN = ROOT / "main.py"
REQ = ROOT / "requirements.txt"
LOG = ROOT / "data" / "boot_run.log"


def log(msg: str) -> None:
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def run(cmd: list[str], cwd: Path | None = None, check: bool = False) -> int:
    log("$ " + " ".join(cmd))
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd or ROOT),
            check=check,
            text=True,
            capture_output=True,
        )
        if p.stdout:
            log(p.stdout.strip())
        if p.stderr:
            log(p.stderr.strip())
        return p.returncode
    except Exception as exc:
        log(f"cmd failed: {exc}")
        return 1


def git_pull() -> None:
    # Wait a bit for network after reboot
    for i in range(12):
        rc = run(["ping", "-c", "1", "-W", "2", "8.8.8.8"])
        if rc == 0:
            break
        log(f"network not ready ({i + 1}/12)...")
        time.sleep(5)

    run(["git", "remote", "update"], cwd=ROOT)
    # discard local tracked edits so pull always wins (device is not a edit machine)
    run(["git", "fetch", "--all"], cwd=ROOT)
    run(["git", "reset", "--hard", "origin/main"], cwd=ROOT)
    # keep config.json / data/ (gitignored)
    log("git reset --hard origin/main done")


def ensure_venv_deps() -> Path:
    py = VENV_PYTHON if VENV_PYTHON.exists() else Path(sys.executable)
    if not VENV_PYTHON.exists():
        log("creating .venv...")
        run([sys.executable, "-m", "venv", str(ROOT / ".venv")], cwd=ROOT)
        py = VENV_PYTHON
    if REQ.exists():
        run([str(py), "-m", "pip", "install", "-q", "-r", str(REQ)], cwd=ROOT)
    return py


def main() -> int:
    os.chdir(ROOT)
    log(f"=== boot_run start cwd={ROOT} ===")

    try:
        git_pull()
    except Exception as exc:
        log(f"git pull skipped/failed: {exc} — starting with existing code")

    py = ensure_venv_deps()
    if not MAIN.exists():
        log(f"missing {MAIN}")
        return 1

    cfg = ROOT / "config.json"
    if not cfg.exists() and (ROOT / "config.example.json").exists():
        run(["cp", str(ROOT / "config.example.json"), str(cfg)])
        log("created config.json from example — edit mqtt/port if needed")

    log(f"exec {py} {MAIN}")
    # Replace this process so systemd tracks main.py
    os.execv(str(py), [str(py), str(MAIN)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
