"""Remote enroll from HR UI via MQTT a:enroll."""

from __future__ import annotations

from typing import Any, Optional

from .fingerprint import R307, FingerprintError, finger_id_to_card
from .mqtt_client import AttendanceMqtt
from .oled import OledDisplay


def next_template_id(sensor: R307, capacity: int) -> int:
    count = sensor.template_count()
    if count >= capacity:
        raise FingerprintError("Sensor library full (1000 max)")
    nxt = count + 1
    if nxt < 1:
        nxt = 1
    if nxt > capacity:
        raise FingerprintError("Sensor library full")
    return nxt


def run_remote_enroll(
    sensor: R307,
    mqtt: AttendanceMqtt,
    job: dict[str, Any],
    *,
    capacity: int = 1000,
    oled: Optional[OledDisplay] = None,
) -> bool:
    timeout_s = float(job.get("timeout_s") or 60)
    hr_user_id = str(job.get("hr_user_id") or "")
    employee_id = str(job.get("employee_id") or "")
    employee_name = str(job.get("employee_name") or "")
    location = job.get("location")
    finger = int(job.get("finger") or 1)
    if finger not in (1, 2):
        finger = 1

    try:
        if location is None:
            location = next_template_id(sensor, capacity)
        else:
            location = int(location)
            if location < 1 or location > capacity:
                raise FingerprintError(f"location must be 1..{capacity}")

        label = employee_name or employee_id or f"#{location}"
        print(f"UI enroll finger {finger}/2 → page {location} ({label})")
        if oled and oled.ready:
            oled.show_lines(f"ENROLL {finger}/2", label[:18], "Place finger 1/2")

        sensor.enroll(location, timeout_s=timeout_s)
        card_id = finger_id_to_card(location)
        msg = f"Finger {finger}/2 enrolled as {card_id}"
        print(msg)
        if oled and oled.ready:
            oled.show_lines("ENROLLED", f"{finger}/2 {card_id}", label[:18])

        mqtt.send_enroll_result(
            ok=True,
            card_id=card_id,
            location=location,
            hr_user_id=hr_user_id,
            employee_id=employee_id,
            message=msg,
            finger=finger,
        )
        return True
    except Exception as exc:
        err = str(exc)
        print(f"UI enroll failed: {err}")
        if oled and oled.ready:
            oled.show_error(801, "ENROLL FAIL", err[:40])
        mqtt.send_enroll_result(
            ok=False,
            card_id="",
            location=location if isinstance(location, int) else None,
            hr_user_id=hr_user_id,
            employee_id=employee_id,
            message=err,
            finger=finger,
        )
        return False
