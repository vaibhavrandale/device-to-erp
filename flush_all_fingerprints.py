#!/usr/bin/env python3
"""
Flush ALL fingerprints from the R307S sensor flash.

WARNING: This deletes every enrolled template on the sensor.
HR user FP#### mappings stay in MongoDB — re-enroll fingers after this.

Usage on Pi:
  cd ~/attendance-erp/device-to-erp   # your clone path
  source .venv/bin/activate
  python3 flush_all_fingerprints.py
"""

from __future__ import annotations

import sys

from taypro.config import load_config, parse_u32
from taypro.fingerprint import R307, FingerprintError, OK


def main() -> int:
    cfg = load_config()
    port = cfg.get("fingerprint_port") or "/dev/ttyUSB0"
    baud = int(cfg.get("fingerprint_baud") or 57600)

    print("=== Flush ALL R307 fingerprints ===")
    print(f"Port: {port} @ {baud}")
    print()
    print("This will DELETE every fingerprint template on the sensor.")
    confirm = input("Type YES to continue: ").strip()
    if confirm != "YES":
        print("Cancelled.")
        return 1

    try:
        sensor = R307.open(
            port=port,
            baudrate=baud,
            address=parse_u32(cfg.get("fingerprint_address"), 0xFFFFFFFF),
            password=parse_u32(cfg.get("fingerprint_password"), 0),
        )
    except (FingerprintError, OSError) as exc:
        print(f"Sensor open failed: {exc}")
        return 1

    try:
        before = sensor.template_count()
        print(f"Templates before: {before}")

        code = sensor.empty()
        if code != OK:
            print(f"empty() failed code=0x{code:02x}")
            return 1

        after = sensor.template_count()
        print(f"Templates after:  {after}")
        print("Done — all fingerprints flushed from R307.")
        print("Re-enroll users from HR UI (Enroll Finger 1 / 2).")
        return 0 if after == 0 else 1
    except FingerprintError as exc:
        print(f"Flush failed: {exc}")
        return 1
    finally:
        sensor.close()


if __name__ == "__main__":
    sys.exit(main())
