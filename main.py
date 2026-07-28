#!/usr/bin/env python3
"""Taypro RasPi 3B + R307S attendance — same MQTT contract as ESP8266 RFID."""

from __future__ import annotations

import signal
import sys
import time

from taypro.boot import boot_register
from taypro.config import load_config, parse_u32
from taypro.fingerprint import R307, FingerprintError, finger_id_to_card
from taypro.mqtt_client import AttendanceMqtt
from taypro.storage import DeviceStorage, hardware_id
from taypro.tap import TapHandler


def main() -> int:
    cfg = load_config()
    storage = DeviceStorage(defaults=cfg)
    hw = hardware_id()
    print("=== Taypro Fingerprint Attendance (RasPi) ===")
    print(f"hardware_id={hw}")
    print(f"MQTT {cfg['mqtt_host']}:{cfg['mqtt_port']}")
    print(f"UART {cfg['fingerprint_port']} @ {cfg['fingerprint_baud']}")

    mqtt = AttendanceMqtt(
        host=cfg["mqtt_host"],
        port=int(cfg["mqtt_port"]),
        topic_up=cfg["topic_up"],
        topic_down_prefix=cfg["topic_down_hw_prefix"],
        storage=storage,
    )

    stop = False

    def _stop(*_args):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    if not mqtt.connect(timeout_s=20):
        print("[ERR-402] Could not connect MQTT — check broker / network")
        return 1

    if not boot_register(mqtt, storage, timeout_s=float(cfg["register_timeout_s"])):
        print("[ERR-601] Boot register incomplete — will keep running; fix HR/broker")
    else:
        mqtt.send_heartbeat()

    try:
        sensor = R307(
            port=cfg["fingerprint_port"],
            baudrate=int(cfg["fingerprint_baud"]),
            address=parse_u32(cfg.get("fingerprint_address"), 0xFFFFFFFF),
            password=parse_u32(cfg.get("fingerprint_password"), 0),
        )
    except (FingerprintError, OSError) as exc:
        print(f"[ERR-201] Fingerprint sensor: {exc}")
        mqtt.disconnect()
        return 1

    try:
        params = sensor.read_sys_params()
        print(
            f"R307 OK capacity={params['capacity']} templates={sensor.template_count()}"
        )
    except FingerprintError as exc:
        print(f"[ERR-201] R307 sys read failed: {exc}")
        sensor.close()
        mqtt.disconnect()
        return 1

    tap = TapHandler(
        mqtt,
        storage,
        debounce_s=float(cfg["finger_debounce_s"]),
        response_timeout_s=float(cfg["tap_response_timeout_s"]),
    )

    last_heartbeat = time.monotonic()
    heartbeat_s = float(cfg["heartbeat_interval_s"])
    poll_s = float(cfg["scan_poll_s"])
    capacity = int(params["capacity"] or 200)

    print("Ready — place finger on R307S")
    print(f"HR card_id format example: {finger_id_to_card(1)}")

    try:
        while not stop:
            if not mqtt.connected():
                time.sleep(1)
                continue

            now = time.monotonic()
            if now - last_heartbeat >= heartbeat_s:
                mqtt.send_heartbeat()
                last_heartbeat = now

            if storage.is_registered() and storage.has_location() and not tap.in_flight:
                try:
                    # search across full library
                    code = sensor.get_image()
                    if code == 0x00:  # OK
                        if sensor.image2tz(1) == 0x00:
                            page = sensor.search(slot=1, start=0, count=capacity)
                            if page is not None:
                                tap.handle_template(page)
                            else:
                                print("Finger seen — no match in sensor library")
                except FingerprintError as exc:
                    print(f"Scan error: {exc}")

            time.sleep(poll_s)
    finally:
        sensor.close()
        mqtt.disconnect()
        print("Stopped")

    return 0


if __name__ == "__main__":
    sys.exit(main())
