#!/usr/bin/env python3
"""Enroll / manage fingerprints on R307S.

Usage on Pi:
  python3 enroll.py                  # enroll next free id
  python3 enroll.py --id 5           # enroll into page 5
  python3 enroll.py --list
  python3 enroll.py --delete 5
  python3 enroll.py --empty          # wipe all templates (dangerous)
"""

from __future__ import annotations

import argparse
import sys

from taypro.config import load_config, parse_u32
from taypro.fingerprint import R307, FingerprintError, finger_id_to_card


def next_free_id(sensor: R307, capacity: int) -> int:
    count = sensor.template_count()
    if count >= capacity:
        raise FingerprintError("Sensor library full")
    # Dense enroll from 1..N when you don't pass --id
    return min(count + 1, capacity)


def main() -> int:
    parser = argparse.ArgumentParser(description="R307S fingerprint enroll for Taypro")
    parser.add_argument("--id", type=int, help="Template page id (1..capacity)")
    parser.add_argument("--list", action="store_true", help="Show sensor capacity / count")
    parser.add_argument("--delete", type=int, metavar="ID", help="Delete one template id")
    parser.add_argument("--empty", action="store_true", help="Delete ALL templates")
    args = parser.parse_args()

    cfg = load_config()
    try:
        sensor = R307(
            port=cfg["fingerprint_port"],
            baudrate=int(cfg["fingerprint_baud"]),
            address=parse_u32(cfg.get("fingerprint_address"), 0xFFFFFFFF),
            password=parse_u32(cfg.get("fingerprint_password"), 0),
        )
    except (FingerprintError, OSError) as exc:
        print(f"Sensor open failed: {exc}")
        return 1

    try:
        params = sensor.read_sys_params()
        capacity = int(params["capacity"] or 200)
        count = sensor.template_count()
        print(f"R307 capacity={capacity} enrolled={count}")

        if args.list:
            print("Assign each enrolled id in HR as card_id, e.g.", finger_id_to_card(1))
            return 0

        if args.empty:
            code = sensor.empty()
            print("empty →", "OK" if code == 0 else f"0x{code:02x}")
            return 0 if code == 0 else 1

        if args.delete is not None:
            code = sensor.delete(args.delete)
            print(f"delete {args.delete} →", "OK" if code == 0 else f"0x{code:02x}")
            return 0 if code == 0 else 1

        location = args.id if args.id is not None else next_free_id(sensor, capacity)
        if location < 1 or location > capacity:
            print(f"id must be 1..{capacity}")
            return 1

        sensor.enroll(location)
        card = finger_id_to_card(location)
        print()
        print(f"Enrolled template #{location}")
        print(f"Put this in HR employee RFID / card_id field: {card}")
        return 0
    except FingerprintError as exc:
        print(f"Enroll failed: {exc}")
        return 1
    finally:
        sensor.close()


if __name__ == "__main__":
    sys.exit(main())
