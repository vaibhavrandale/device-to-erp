#!/usr/bin/env python3
"""Run on the Pi monitor (no SSH needed): python3 diagnose.py"""

from __future__ import annotations

import glob
import sys
import time

import serial

from taypro.config import load_config, parse_u32
from taypro.fingerprint import POWER_HINT, R307, FingerprintError


def list_ports() -> list[str]:
    return sorted(glob.glob("/dev/ttyUSB*") + glob.glob("/dev/ttyACM*") + glob.glob("/dev/serial0"))


def raw_ping(port: str, baud: int) -> bytes:
    # verify password packet, default addr/password
    pkt = bytes.fromhex("EF01FFFFFFFF0100071300000000001B")
    with serial.Serial(port=port, baudrate=baud, timeout=1.5) as ser:
        time.sleep(0.2)
        ser.reset_input_buffer()
        ser.write(pkt)
        time.sleep(0.4)
        return ser.read(64)


def main() -> int:
    print("=== Taypro R307 diagnose ===")
    print(POWER_HINT)

    ports = list_ports()
    print("Serial ports found:", ports or "(none)")
    if not ports:
        print("Plug CP2102 into Pi USB, then run again.")
        return 1

    cfg = load_config()
    preferred = cfg.get("fingerprint_port") or "/dev/ttyUSB0"
    if preferred not in ports:
        preferred = ports[0]
    print(f"Using port: {preferred}")

    print("\n1) Raw ping (any reply bytes?)")
    any_bytes = False
    for baud in (57600, 9600, 115200, 19200):
        try:
            data = raw_ping(preferred, baud)
        except OSError as exc:
            print(f"  cannot open {preferred}: {exc}")
            return 1
        print(f"  @{baud}: got {len(data)} bytes {data.hex() if data else 'NOTHING'}")
        if data:
            any_bytes = True

    if not any_bytes:
        print("\nFAIL: USB port works, sensor silent.")
        print("Fix power first: R307 VCC -> Pi 5V (pin 2), LED must stay ON.")
        print("Then swap TX/RX once if still NOTHING.")
        return 1

    print("\n2) Protocol open (auto baud)")
    try:
        sensor = R307.open(
            port=preferred,
            baudrate=int(cfg.get("fingerprint_baud") or 57600),
            address=parse_u32(cfg.get("fingerprint_address"), 0xFFFFFFFF),
            password=parse_u32(cfg.get("fingerprint_password"), 0),
        )
    except FingerprintError as exc:
        print(exc)
        return 1

    try:
        p = sensor.read_sys_params()
        print(f"OK capacity={p['capacity']} templates={sensor.template_count()}")
        print(f"\nUpdate config.json:\n  fingerprint_port: {preferred}")
        return 0
    finally:
        sensor.close()


if __name__ == "__main__":
    sys.exit(main())
