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

import json
import os
import subprocess
import sys
import time
from pathlib import Path

SELF = Path(__file__).resolve()
ROOT = SELF.parent.parent
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


def run(cmd: list[str], cwd: Path | None = None, check: bool = False, timeout: int = 300) -> int:
    log("$ " + " ".join(cmd))
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd or ROOT),
            check=check,
            text=True,
            capture_output=True,
            # A credential prompt on the private repo would block forever, and systemd
            # never restarts a hung process. Fail fast instead and run existing code.
            env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            timeout=timeout,
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


def restart_self_if_updated(before: bytes) -> None:
    """git pull writes a new boot_run.py to disk, but this process is still running
    the old code it loaded at startup. Re-exec so an update to this file takes
    effect on the same boot instead of the one after it."""
    if os.environ.get("TAYPRO_BOOT_REEXEC") == "1":
        return  # already restarted once this boot; never loop
    try:
        after = SELF.read_bytes()
    except OSError:
        return
    if after == before:
        return
    log("boot_run.py updated by git - restarting with the new version")
    os.environ["TAYPRO_BOOT_REEXEC"] = "1"
    os.execv(sys.executable, [sys.executable, str(SELF)])


def sync_deployed_config() -> None:
    """Merge every tracked setting into the Pi's gitignored config.json."""
    cfg_path = ROOT / "config.json"
    deploy_path = ROOT / "config.deploy.json"
    if not deploy_path.exists():
        return
    try:
        deployed = json.loads(deploy_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log(f"config.deploy.json unreadable ({exc}) - keeping existing config.json")
        return

    if not cfg_path.exists():
        cfg_path.write_text(json.dumps(deployed, indent=2) + "\n", encoding="utf-8")
        log("created config.json from deployed config")
        return

    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        log(f"config.json unreadable ({exc}) - recreating from deployed config")
        cfg_path.write_text(json.dumps(deployed, indent=2) + "\n", encoding="utf-8")
        return

    changed = [
        key for key, value in deployed.items() if key not in cfg or cfg[key] != value
    ]
    if not changed:
        return
    for key in changed:
        cfg[key] = deployed[key]
    cfg_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
    log(f"config.json updated from repo: {', '.join(changed)}")


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
        self_before = SELF.read_bytes()
    except OSError:
        self_before = b""

    try:
        git_pull()
    except Exception as exc:
        log(f"git pull skipped/failed: {exc} — starting with existing code")

    if self_before:
        restart_self_if_updated(self_before)

    py = ensure_venv_deps()
    if not MAIN.exists():
        log(f"missing {MAIN}")
        return 1

    sync_deployed_config()

    log(f"exec {py} {MAIN}")
    # Replace this process so systemd tracks main.py
    os.execv(str(py), [str(py), str(MAIN)])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
