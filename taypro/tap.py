from __future__ import annotations

import time
from typing import Optional

from .fingerprint import finger_id_to_card
from .mqtt_client import AttendanceMqtt
from .storage import DeviceStorage


class TapHandler:
    def __init__(
        self,
        mqtt: AttendanceMqtt,
        storage: DeviceStorage,
        debounce_s: float = 2.0,
        response_timeout_s: float = 12.0,
    ):
        self.mqtt = mqtt
        self.storage = storage
        self.debounce_s = debounce_s
        self.response_timeout_s = response_timeout_s
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
            return
        if not self.storage.has_location():
            print("[ERR-706] NO LOCATION — set lat/lng in HR dashboard")
            return
        if self.in_flight:
            return
        if not self.mqtt.connected():
            print("[ERR-702] MQTT not connected")
            return

        print(f"Finger match template={template_id} → c={card_id}")
        self.in_flight = True
        try:
            if not self.mqtt.send_tap(card_id):
                print("[ERR-702] SEND FAILED")
                return
            if not self.mqtt.wait_tap(self.response_timeout_s):
                print("[ERR-703] NO RESPONSE — server did not reply in time")
                return
            if self.mqtt.tap_ok:
                print(
                    f"Tap OK — {self.mqtt.tap_employee} ({self.mqtt.tap_punch_type or 'punch'})"
                )
            else:
                msg = self.mqtt.tap_message or "Rejected by server"
                print(f"[ERR-704] TAP FAILED — {msg}")
        finally:
            self.mqtt.reset_tap_wait()
            self.in_flight = False
