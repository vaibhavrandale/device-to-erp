"""Device logs → MQTT a:log → backend AttendanceDeviceLog (same as ESP8266)."""

from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Deque, Optional

if TYPE_CHECKING:
    from .mqtt_client import AttendanceMqtt

ROOT = Path(__file__).resolve().parent.parent
LOG_FILE = ROOT / "data" / "device.log"
PENDING_MAX = 80
SYNC_INTERVAL_S = 10.0


class DeviceLogger:
    def __init__(self) -> None:
        self.boot_id = int(time.time())
        self._pending: Deque[dict] = deque(maxlen=PENDING_MAX)
        self._lock = threading.Lock()
        self._last_sync = 0.0
        self._mqtt: Optional["AttendanceMqtt"] = None
        self._started = time.monotonic()
        self.sync_interval_s = SYNC_INTERVAL_S
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

    def bind_mqtt(self, mqtt: "AttendanceMqtt", sync_interval_s: float | None = None) -> None:
        self._mqtt = mqtt
        if sync_interval_s is not None:
            self.sync_interval_s = float(sync_interval_s)

    def _device_ms(self) -> int:
        return int((time.monotonic() - self._started) * 1000)

    def log(self, message: str) -> None:
        msg = str(message or "").strip()
        if not msg:
            return
        stamp = datetime.now().strftime("%H:%M:%S")
        line = f"[{stamp}] {msg}"
        print(line, flush=True)
        try:
            with LOG_FILE.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass
        with self._lock:
            self._pending.append({"m": line, "t": self._device_ms()})

    def problem(self, area: str, detail: str) -> None:
        self.log(f"{area} problem — {detail}")

    def sync(self, force: bool = False) -> bool:
        mqtt = self._mqtt
        if not mqtt or not mqtt.connected():
            return False
        if not mqtt.storage.is_registered():
            return False

        now = time.monotonic()
        if not force and now - self._last_sync < self.sync_interval_s:
            return False

        with self._lock:
            if not self._pending:
                self._last_sync = now
                return False
            batch = list(self._pending)
            self._pending.clear()

        ok = mqtt.send_logs(boot_id=self.boot_id, lines=batch)
        self._last_sync = now
        if not ok:
            with self._lock:
                for item in reversed(batch):
                    self._pending.appendleft(item)
            return False
        return True


# process-wide logger (ESP had globals too)
device_log = DeviceLogger()
