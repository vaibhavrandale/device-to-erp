from __future__ import annotations

import time
from typing import Optional

from .fingerprint import finger_id_to_fp
from .leds import StatusLeds
from .logger import device_log
from .mqtt_client import AttendanceMqtt
from .oled import OledDisplay
from .storage import DeviceStorage


class TapHandler:
    """Fingerprint punch → MQTT (field c=FP####). No RFID card reader."""

    def __init__(
        self,
        mqtt: AttendanceMqtt,
        storage: DeviceStorage,
        debounce_s: float = 2.0,
        response_timeout_s: float = 12.0,
        oled: Optional[OledDisplay] = None,
        leds: Optional[StatusLeds] = None,
    ):
        self.mqtt = mqtt
        self.storage = storage
        self.debounce_s = debounce_s
        self.response_timeout_s = response_timeout_s
        self.oled = oled
        self.leds = leds
        self.last_fp: Optional[str] = None
        self.last_ms = 0.0
        self.in_flight = False
        self.cooldown_s = max(float(debounce_s), 10.0)

    def handle_template(self, template_id: int) -> bool:
        fp_id = finger_id_to_fp(template_id)
        now = time.monotonic()

        if self.in_flight:
            return False
        if self.last_ms and (now - self.last_ms) < self.cooldown_s:
            left = self.cooldown_s - (now - self.last_ms)
            print(f"Punch ignored — cooldown {left:.0f}s left")
            device_log.log(f"Finger ignored — wait {left:.0f}s")
            if self.oled:
                self.oled.show_ignored(left)
            return False

        if not self.storage.is_registered():
            print("[ERR-701] NOT READY — register incomplete")
            if self.leds:
                self.leds.trigger_fail()
            if self.oled:
                self.oled.show_error(701, "NOT READY", "Device not registered to cloud")
            return False
        if not self.storage.has_location():
            print("[ERR-706] NO LOCATION — set lat/lng in HR dashboard")
            if self.leds:
                self.leds.trigger_fail()
            if self.oled:
                self.oled.show_error(706, "NO LOCATION", "Set device lat/lng in HR")
            return False
        if not self.mqtt.connected():
            print("[ERR-702] MQTT not connected")
            if self.leds:
                self.leds.trigger_fail()
            if self.oled:
                self.oled.show_error(702, "NO CLOUD", "MQTT disconnected — check network")
            return False

        self.in_flight = True
        self.last_fp = fp_id
        self.last_ms = now

        print(f"Finger match template={template_id} → {fp_id}")
        device_log.log(f"Finger punch — {fp_id}")
        if self.oled:
            self.oled.show_processing(fp_id)
        try:
            if not self.mqtt.send_punch(fp_id):
                print("[ERR-702] SEND FAILED")
                device_log.problem("Punch", "MQTT publish failed")
                if self.leds:
                    self.leds.trigger_fail()
                if self.oled:
                    self.oled.show_error(702, "SEND FAILED", "Could not publish punch", fp_id)
                return True
            if not self.mqtt.wait_tap(self.response_timeout_s):
                print("[ERR-703] NO RESPONSE — server did not reply in time")
                device_log.problem("Punch", "Server timeout")
                if self.leds:
                    self.leds.trigger_fail()
                if self.oled:
                    self.oled.show_error(703, "NO RESPONSE", "Server timeout — try again", fp_id)
                return True
            if self.mqtt.tap_ok:
                print(
                    f"Punch OK — {self.mqtt.tap_employee} ({self.mqtt.tap_punch_type or 'punch'})"
                )
                device_log.log(
                    f"Punch OK — {self.mqtt.tap_employee} ({self.mqtt.tap_punch_type or 'punch'})"
                )
                if self.leds:
                    self.leds.trigger_ok()
                if self.oled:
                    self.oled.show_punch_ok(
                        self.mqtt.tap_employee,
                        self.mqtt.tap_punch_type,
                        fp_id=fp_id,
                    )
            else:
                msg = self.mqtt.tap_message or "Rejected by server"
                print(f"[ERR-704] PUNCH FAILED — {msg}")
                device_log.problem("Punch", msg)
                if self.leds:
                    self.leds.trigger_fail()
                if self.oled:
                    lower = msg.lower()
                    if "not registered" in lower or "fingerprint" in lower:
                        self.oled.show_error(
                            704,
                            "NOT ENROLLED",
                            "Finger not linked to any employee",
                            "Ask HR to enroll",
                        )
                    else:
                        self.oled.show_error(704, "REJECTED", msg, fp_id)
            return True
        finally:
            self.mqtt.reset_tap_wait()
            self.in_flight = False
            self.last_ms = time.monotonic()
