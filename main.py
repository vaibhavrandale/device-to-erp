#!/usr/bin/env python3
"""Taypro RasPi fingerprint attendance — MQTT punch + OLED for remote sites."""

from __future__ import annotations

import signal
import sys
import time

from taypro.boot import boot_register
from taypro.config import load_config, parse_u32
from taypro.enroll_remote import run_remote_enroll
from taypro.fingerprint import R307, FingerprintError, finger_id_to_fp
from taypro.mqtt_client import AttendanceMqtt
from taypro.oled import create_oled
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

    oled = create_oled(cfg)
    if oled and oled.ready:
        oled.show_splash()
        time.sleep(1.0)

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

    if oled and oled.ready:
        oled.show_boot("..", "  ", "  ", "Connecting cloud...", device_id=storage.device_id)

    if not mqtt.connect(timeout_s=20):
        print("[ERR-402] Could not connect MQTT — check broker / network")
        if oled and oled.ready:
            oled.show_error(402, "MQTT FAIL", "Cannot reach broker. Check WiFi/IP.", cfg["mqtt_host"])
        return 1

    ip = mqtt._local_ip()
    if oled and oled.ready:
        oled.set_status_meta(ip=ip, extra=f"hw:{hw[-6:]}")
        oled.show_boot("OK", "OK", "..", "Registering...", ip=ip, device_id=storage.device_id)

    if not boot_register(mqtt, storage, timeout_s=float(cfg["register_timeout_s"])):
        print("[ERR-601] Boot register incomplete — will keep running; fix HR/broker")
        if oled and oled.ready:
            oled.show_boot("OK", "OK", "!!", "Register failed", ip=ip, device_id=storage.device_id)
    else:
        mqtt.send_heartbeat()
        if oled and oled.ready:
            oled.show_register_result(
                False,
                storage.device_id,
                f"Online {ip}",
            )
            time.sleep(1.2)

    try:
        sensor = R307.open(
            port=cfg["fingerprint_port"],
            baudrate=int(cfg["fingerprint_baud"]),
            address=parse_u32(cfg.get("fingerprint_address"), 0xFFFFFFFF),
            password=parse_u32(cfg.get("fingerprint_password"), 0),
        )
    except (FingerprintError, OSError) as exc:
        print(f"[ERR-201] Fingerprint sensor: {exc}")
        if oled and oled.ready:
            oled.show_error(201, "SENSOR FAIL", str(exc), cfg["fingerprint_port"])
        mqtt.disconnect()
        return 1

    try:
        params = sensor.read_sys_params()
        templates = sensor.template_count()
        print(f"R307 OK capacity={params['capacity']} templates={templates}")
    except FingerprintError as exc:
        print(f"[ERR-201] R307 sys read failed: {exc}")
        if oled and oled.ready:
            oled.show_error(201, "SENSOR FAIL", str(exc))
        sensor.close()
        mqtt.disconnect()
        return 1

    tap = TapHandler(
        mqtt,
        storage,
        debounce_s=float(cfg["finger_debounce_s"]),
        response_timeout_s=float(cfg["tap_response_timeout_s"]),
        oled=oled if (oled and oled.ready) else None,
    )

    last_heartbeat = time.monotonic()
    last_ui = 0.0
    heartbeat_s = float(cfg["heartbeat_interval_s"])
    poll_s = float(cfg["scan_poll_s"])
    capacity = int(params["capacity"] or 200)

    print("Ready — scan finger")
    print(f"Fingerprint id example: {finger_id_to_fp(1)}")
    if oled and oled.ready:
        oled.showing_tap = False
        oled.set_status_meta(ip=ip, extra=f"hw:{hw[-6:]}")
        oled.show_ready(
            storage,
            wifi_ok=True,
            mqtt_ok=mqtt.connected(),
            templates=templates,
        )

    wait_lift = False
    lift_streak = 0

    try:
        while not stop:
            if not mqtt.connected():
                if oled and oled.ready:
                    oled.show_boot(
                        "OK",
                        "!!",
                        "OK" if storage.is_registered() else "!!",
                        "Reconnecting MQTT...",
                        ip=ip,
                        device_id=storage.device_id,
                    )
                time.sleep(1)
                continue

            now = time.monotonic()
            if now - last_heartbeat >= heartbeat_s:
                mqtt.send_heartbeat()
                last_heartbeat = now
                ip = mqtt._local_ip()
                if oled and oled.ready:
                    oled.set_status_meta(ip=ip, extra=f"hw:{hw[-6:]}")

            if oled and oled.ready:
                oled.poll_clear_temp(storage, mqtt_ok=mqtt.connected())
                if not oled.showing_tap and now - last_ui >= 1.0:
                    try:
                        templates = sensor.template_count()
                    except FingerprintError:
                        pass
                    oled.show_ready(
                        storage,
                        wifi_ok=True,
                        mqtt_ok=mqtt.connected(),
                        templates=templates,
                    )
                    last_ui = now

            if mqtt.enroll_pending and not tap.in_flight:
                job = mqtt.enroll_pending
                mqtt.enroll_pending = None
                wait_lift = True
                lift_streak = 0
                run_remote_enroll(
                    sensor,
                    mqtt,
                    job,
                    capacity=capacity,
                    oled=oled if (oled and oled.ready) else None,
                )
                time.sleep(poll_s)
                continue

            if storage.is_registered() and storage.has_location() and not tap.in_flight:
                try:
                    img = sensor.get_image()
                    if wait_lift:
                        if img == 0x02:
                            lift_streak += 1
                            if lift_streak >= 5:
                                wait_lift = False
                                lift_streak = 0
                                print("Finger lifted — ready for next scan")
                        else:
                            lift_streak = 0
                    elif img == 0x00:
                        if sensor.image2tz(1) == 0x00:
                            page = sensor.search(slot=1, start=0, count=capacity)
                            if page is not None:
                                wait_lift = True
                                lift_streak = 0
                                tap.handle_template(page)
                            else:
                                print("Finger seen — no match in sensor library")
                                if oled and oled.ready:
                                    oled.show_no_match()
                                wait_lift = True
                                lift_streak = 0
                except FingerprintError as exc:
                    print(f"Scan error: {exc}")
                    if oled and oled.ready:
                        oled.show_error(201, "SCAN ERR", str(exc))

            time.sleep(poll_s)
    finally:
        sensor.close()
        mqtt.disconnect()
        if oled and oled.ready:
            oled.show_lines("STOPPED", "Service ended", "Reboot to restart")
        print("Stopped")

    return 0


if __name__ == "__main__":
    sys.exit(main())
