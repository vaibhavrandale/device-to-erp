from __future__ import annotations

import json
import socket
import threading
import time
from typing import Any, Callable, Optional

import paho.mqtt.client as mqtt

from .storage import DeviceStorage, hardware_id


class AttendanceMqtt:
    def __init__(
        self,
        host: str,
        port: int,
        topic_up: str,
        topic_down_prefix: str,
        storage: DeviceStorage,
        on_message: Optional[Callable[[dict[str, Any]], None]] = None,
        username: str = "",
        password: str = "",
        tls: bool = False,
    ):
        self.host = host
        self.port = port
        self.topic_up = topic_up
        self.topic_down_prefix = topic_down_prefix
        self.storage = storage
        self.hw = hardware_id()
        self.on_message = on_message
        self._connected = threading.Event()
        client_id = f"taypro-{self.hw}"
        try:
            self.client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION2,
                client_id=client_id,
            )
        except (AttributeError, TypeError):
            # paho-mqtt 1.x
            self.client = mqtt.Client(client_id=client_id)
        if username:
            self.client.username_pw_set(username, password or None)
        if tls:
            # System CA bundle: enough for managed brokers (Amazon MQ / AWS IoT),
            # which present a publicly trusted certificate.
            self.client.tls_set()
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_mqtt_message

        # replies
        self.register_reply = False
        self.register_ok = False
        self.register_created = False
        self.register_message = ""
        self.tap_reply = False
        self.tap_ok = False
        self.tap_message = ""
        self.tap_employee = ""
        self.tap_punch_type = ""
        self.tap_card_id = ""
        self.enroll_pending = None
        self.enroll_ack = None

    @property
    def down_topic(self) -> str:
        return f"{self.topic_down_prefix}{self.hw}"

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        # paho 1.x: reason_code is rc int; paho 2.x: ReasonCode / flags differ
        rc = reason_code
        if hasattr(reason_code, "value"):
            rc = reason_code.value
        # paho 1.x signature is (client, userdata, flags, rc)
        if isinstance(flags, int) and properties is None and not hasattr(reason_code, "value"):
            # called as paho1 with (client, userdata, flags, rc) — flags is dict actually
            pass
        ok = (rc == 0)
        if ok:
            client.subscribe(self.down_topic)
            self._connected.set()
            print(f"MQTT connected — subscribed {self.down_topic}")
        else:
            print(f"MQTT connect failed: {reason_code}")

    def _on_disconnect(self, client, userdata, *args):
        self._connected.clear()
        print(f"MQTT disconnected: {args[0] if args else '?'}")

    def _on_mqtt_message(self, client, userdata, msg):
        try:
            doc = json.loads(msg.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            print(f"[ERR-404] Bad JSON on down topic: {exc}")
            return
        if msg.topic != self.down_topic:
            return
        self._handle_down(doc)
        if self.on_message:
            self.on_message(doc)

    def _handle_down(self, doc: dict[str, Any]) -> None:
        action = doc.get("a") or doc.get("action") or ""
        if action == "register":
            self.register_reply = True
            self.register_ok = bool(doc.get("ok") or doc.get("success"))
            self.register_created = bool(doc.get("created"))
            self.register_message = str(doc.get("message") or doc.get("msg") or "")
            if self.register_ok:
                if doc.get("device_id"):
                    self.storage.device_id = self.storage.normalize_device_id(doc["device_id"])
                if doc.get("device_name"):
                    self.storage.device_name = str(doc["device_name"]).strip()
                key = doc.get("k") or doc.get("device_key")
                if key:
                    self.storage.device_key = str(key).strip()
                self.storage.save()
            return

        if action == "config":
            self.storage.apply_config(doc)
            print("HR config updated on device")
            return

        if action == "tap":
            self.tap_reply = True
            self.tap_ok = bool(doc.get("ok") or doc.get("success"))
            self.tap_message = str(doc.get("message") or doc.get("msg") or "")
            self.tap_employee = str(doc.get("employee_name") or "-")
            self.tap_punch_type = str(doc.get("punch_type") or "")
            self.tap_card_id = str(doc.get("card_id") or doc.get("c") or "")
            return

        if action == "enroll":
            loc = doc.get("location")
            try:
                loc = int(loc) if loc is not None and str(loc).strip() != "" else None
            except (TypeError, ValueError):
                loc = None
            self.enroll_pending = {
                "hr_user_id": str(doc.get("hr_user_id") or ""),
                "employee_id": str(doc.get("employee_id") or ""),
                "employee_name": str(doc.get("employee_name") or ""),
                "location": loc,
                "finger": int(doc.get("finger") or 1),
                "timeout_s": float(doc.get("timeout_s") or 60),
            }
            print(
                f"Enroll requested finger={self.enroll_pending['finger']}/2"
                f" employee={self.enroll_pending['employee_name'] or self.enroll_pending['employee_id'] or '?'}"
                f" location={loc or 'auto'}"
            )
            return

        if action == "enroll_result":
            self.enroll_ack = doc
            return

    def connect(self, timeout_s: float = 15.0) -> bool:
        try:
            self.client.connect(self.host, self.port, keepalive=30)
        except (OSError, socket.error) as exc:
            print(f"[ERR-402] Broker unreachable: {exc}")
            return False
        self.client.loop_start()
        if not self._connected.wait(timeout_s):
            print("[ERR-402] MQTT connect timeout")
            return False
        return True

    def disconnect(self) -> None:
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass

    def connected(self) -> bool:
        return self._connected.is_set()

    def publish_up(self, payload: dict[str, Any]) -> bool:
        body = json.dumps(payload, separators=(",", ":"))
        info = self.client.publish(self.topic_up, body, qos=0, retain=False)
        try:
            info.wait_for_publish(timeout=5)
            return info.is_published()
        except Exception as exc:
            print(f"[ERR-403] Publish failed: {exc}")
            return False

    def _local_ip(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect((self.host, self.port))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except OSError:
            return "0.0.0.0"

    def reset_register_wait(self) -> None:
        self.register_reply = False
        self.register_ok = False
        self.register_created = False
        self.register_message = ""

    def reset_tap_wait(self) -> None:
        self.tap_reply = False
        self.tap_ok = False
        self.tap_message = ""
        self.tap_employee = ""
        self.tap_punch_type = ""
        self.tap_card_id = ""

    def send_register(self) -> bool:
        self.reset_register_wait()
        return self.publish_up(
            {
                "a": "register",
                "hw": self.hw,
                "d": self.storage.device_id,
                "k": self.storage.device_key,
                "n": self.storage.device_name,
                "w": "raspi",
                "ip": self._local_ip(),
            }
        )

    def send_heartbeat(self) -> bool:
        return self.publish_up(
            {
                "a": "heartbeat",
                "hw": self.hw,
                "d": self.storage.device_id,
                "k": self.storage.device_key,
                "n": self.storage.device_name,
                "w": "raspi",
                "p": 0,
                "ip": self._local_ip(),
            }
        )

    def send_punch(self, fp_id: str) -> bool:
        """Publish fingerprint punch (MQTT a:tap, c=FP####)."""
        if not self.storage.has_location():
            print("[ERR-701] Latitude/longitude not set on device")
            return False
        self.reset_tap_wait()
        return self.publish_up(
            {
                "a": "tap",
                "hw": self.hw,
                "d": self.storage.device_id,
                "k": self.storage.device_key,
                "c": fp_id,
                "latitude": self.storage.latitude,
                "longitude": self.storage.longitude,
                "la": self.storage.latitude,
                "lo": self.storage.longitude,
            }
        )

    # alias used by older call sites
    def send_tap(self, card_id: str) -> bool:
        return self.send_punch(card_id)

    def send_enroll_result(
        self,
        *,
        ok: bool,
        card_id: str = "",
        location: int | None = None,
        hr_user_id: str = "",
        employee_id: str = "",
        message: str = "",
        finger: int = 1,
    ) -> bool:
        payload: dict[str, Any] = {
            "a": "enroll_result",
            "hw": self.hw,
            "d": self.storage.device_id,
            "k": self.storage.device_key,
            "ok": ok,
            "success": ok,
            "c": card_id,
            "card_id": card_id,
            "hr_user_id": hr_user_id,
            "employee_id": employee_id,
            "finger": int(finger) if finger else 1,
            "message": message,
        }
        if location is not None:
            payload["location"] = location
        return self.publish_up(payload)

    def send_logs(self, *, boot_id: int, lines: list[dict[str, Any]]) -> bool:
        """Same shape as ESP DeviceLogger → processDeviceLogs."""
        if not lines:
            return True
        return self.publish_up(
            {
                "a": "log",
                "hw": self.hw,
                "d": self.storage.device_id,
                "k": self.storage.device_key,
                "boot_id": int(boot_id),
                "lines": lines,
            }
        )

    def wait_register(self, timeout_s: float) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self.register_reply:
                return True
            time.sleep(0.05)
        return False

    def wait_tap(self, timeout_s: float) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self.tap_reply:
                return True
            time.sleep(0.05)
        return False
