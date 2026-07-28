#!/usr/bin/env python3
"""Quick OLED test: python3 test_oled.py"""

from __future__ import annotations

import time

from taypro.config import load_config
from taypro.oled import create_oled
from taypro.storage import DeviceStorage


def main() -> int:
    cfg = load_config()
    oled = create_oled(cfg)
    if not oled or not oled.ready:
        print("OLED init failed — enable I2C and check wiring")
        return 1
    storage = DeviceStorage(defaults=cfg)
    oled.show_splash()
    time.sleep(1.2)
    oled.show_boot("OK", "OK", "OK", "OLED test")
    time.sleep(1.5)
    oled.show_ready(storage, True, True)
    time.sleep(1.5)
    oled.show_tap_ok("Mayuresh Dhangar", "check_in")
    time.sleep(2)
    oled.show_error(704, "NOT FOUND", "Finger not in HR", "FP0001")
    time.sleep(2)
    oled.show_ready(storage, True, True)
    print("OLED test done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
