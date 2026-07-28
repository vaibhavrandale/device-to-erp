#!/usr/bin/env python3
"""Minimal self-check (no hardware)."""

from taypro.fingerprint import finger_id_to_card
from taypro.storage import DeviceStorage


def main() -> None:
    assert finger_id_to_card(1) == "FP0001"
    assert finger_id_to_card(42) == "FP0042"
    s = DeviceStorage.__new__(DeviceStorage)
    s.device_id = "unassigned"
    s.device_key = ""
    s.latitude = None
    s.longitude = None
    assert not s.is_registered()
    s.device_id = "office-gate"
    s.device_key = "abc"
    assert s.is_registered()
    s.latitude = 19.07
    s.longitude = 72.87
    assert s.has_location()
    print("self-check OK")


if __name__ == "__main__":
    main()
