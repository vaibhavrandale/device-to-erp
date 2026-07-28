from __future__ import annotations

import time
from typing import Optional

from .fingerprint import finger_id_to_card
from .mqtt_client import AttendanceMqtt
from .oled import OledDisplay
from .storage import DeviceStorage


class TapHandler:
    def __init__(
        self,
        mqtt: AttendanceMqtt,
        storage: DeviceStorage,
        debounce_s: float = 2.0,
        response_timeout_s: float = 12.0,
        oled: Optional[OledDisplay] = None,
    ):
        self.mqtt = mqtt
        self.storage = storage
        self.debounce_s = debounce_s
        self.response_timeout_s = response_timeout_s
        self.oled = oled
        self.last_card: Optional[str] = None
        self.last_ms = 0.0
        self.in_flight = False

    def handle_template(self, template_id: int) -> None:
        card_id = finger_id_to_card(template_id)
        now = time.monotonic()
        if card_id == self.last_card and (now - self.last_ms) < self.debounce_s:
            return
        self.last_card = card_id
        self.last_ms = now

        if not self.storage.is_registered():
            print("[ERR-701] NOT READY — register incomplete")
            if self.oled:
                self.oled.show_error(701, "NOT READY", "Wait for register")
            return
        if not self.storage.has_location():
            print("[ERR-706] NO LOCATION — set lat/lng in HR dashboard")
            if self.oled:
                self.oled.show_error(706, "NO LOCATION", "Set lat/lng in HR")
            return
        if self.in_flight:
            return
        if not self.mqtt.connected():
            print("[ERR-702] MQTT not connected")
            if self.oled:
                self.oled.show_error(702, "NO MQTT", "Cloud disconnected")
            return

        print(f"Finger match template={template_id} → c={card_id}")
        self.in_flight = True
        if self.oled:
            self.oled.show_processing(card_id)
        try:
            if not self.mqtt.send_tap(card_id):
                print("[ERR-702] SEND FAILED")
                if self.oled:
                    self.oled.show_error(702, "SEND FAILED", "MQTT publish failed", card_id)
                return
            if not self.mqtt.wait_tap(self.response_timeout_s):
                print("[ERR-703] NO RESPONSE — server did not reply in time")
                if self.oled:
                    self.oled.show_error(703, "NO RESPONSE", "Server timeout", card_id)
                return
            if self.mqtt.tap_ok:
                print(
                    f"Tap OK — {self.mqtt.tap_employee} ({self.mqtt.tap_punch_type or 'punch'})"
                )
                if self.oled:
                    self.oled.show_tap_ok(self.mqtt.tap_employee, self.mqtt.tap_punch_type)
            else:
                msg = self.mqtt.tap_message or "Rejected by server"
                print(f"[ERR-704] TAP FAILED — {msg}")
                if self.oled:
                    title = "NOT FOUND" if "not registered" in msg.lower() else "TAP FAILED"
                    self.oled.show_error(704, title, msg, card_id)
        finally:
            self.mqtt.reset_tap_wait()
            self.in_flight = False
