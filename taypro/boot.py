from __future__ import annotations

from .mqtt_client import AttendanceMqtt
from .storage import DeviceStorage


def boot_register(mqtt: AttendanceMqtt, storage: DeviceStorage, timeout_s: float = 15.0) -> bool:
    if storage.is_registered():
        print(f"Register — using saved device id {storage.device_id}")
        return True

    print("Register — asking server if device exists")
    if not mqtt.send_register():
        print("[ERR-602] Register publish failed")
        return False

    if not mqtt.wait_register(timeout_s):
        print("[ERR-603] Register timeout")
        return False

    if not mqtt.register_ok:
        msg = mqtt.register_message or "Registration rejected"
        print(f"[ERR-604] NOT REGISTERED — {msg}")
        return False

    kind = "created" if mqtt.register_created else "linked"
    print(f"Device {kind} on server | id {storage.device_id}")
    return True
