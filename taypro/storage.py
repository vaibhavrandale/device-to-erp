from __future__ import annotations

import json
import math
import uuid
from pathlib import Path
from typing import Any

from .config import DEVICE_CFG_PATH


def hardware_id() -> str:
    """Stable 12-char hex id (same shape as ESP MAC) from Pi CPU serial / machine-id."""
    for path in (Path("/proc/cpuinfo"), Path("/etc/machine-id")):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if path.name == "cpuinfo":
            for line in text.splitlines():
                if line.lower().startswith("serial"):
                    raw = line.split(":")[-1].strip().lower().replace(" ", "")
                    if raw and raw != "0000000000000000":
                        return raw[-12:].zfill(12)
        else:
            raw = text.strip().lower().replace("-", "")
            if len(raw) >= 12:
                return raw[:12]
    return uuid.getnode().to_bytes(6, "big").hex()


class DeviceStorage:
    def __init__(self, path: Path | None = None, defaults: dict[str, Any] | None = None):
        self.path = path or DEVICE_CFG_PATH
        defaults = defaults or {}
        self.device_id = str(defaults.get("device_id") or "unassigned")
        self.device_name = str(defaults.get("device_name") or "Taypro Fingerprint")
        self.device_key = str(defaults.get("device_key") or "")
        self.latitude = defaults.get("latitude")
        self.longitude = defaults.get("longitude")
        self.load()

    def load(self) -> None:
        if not self.path.exists():
            return
        try:
            with self.path.open("r", encoding="utf-8") as f:
                doc = json.load(f)
        except (OSError, json.JSONDecodeError):
            return
        if doc.get("device_id"):
            self.device_id = self.normalize_device_id(doc["device_id"])
        if doc.get("device_name"):
            self.device_name = str(doc["device_name"]).strip()
        if doc.get("device_key"):
            self.device_key = str(doc["device_key"]).strip()
        if "latitude" in doc and doc["latitude"] is not None:
            self.latitude = float(doc["latitude"])
        if "longitude" in doc and doc["longitude"] is not None:
            self.longitude = float(doc["longitude"])

    def save(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        doc: dict[str, Any] = {
            "device_id": self.device_id,
            "device_name": self.device_name,
            "device_key": self.device_key,
        }
        if self.latitude is not None and not (isinstance(self.latitude, float) and math.isnan(self.latitude)):
            doc["latitude"] = self.latitude
        if self.longitude is not None and not (isinstance(self.longitude, float) and math.isnan(self.longitude)):
            doc["longitude"] = self.longitude
        try:
            with self.path.open("w", encoding="utf-8") as f:
                json.dump(doc, f, indent=2)
            return True
        except OSError:
            return False

    @staticmethod
    def normalize_device_id(value: str) -> str:
        return str(value).strip().lower()

    def is_registered(self) -> bool:
        return bool(self.device_id) and self.device_id != "unassigned" and bool(self.device_key)

    def has_location(self) -> bool:
        try:
            lat = float(self.latitude)
            lng = float(self.longitude)
        except (TypeError, ValueError):
            return False
        return -90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0

    def apply_config(self, doc: dict[str, Any]) -> bool:
        """Apply HR config push. Returns True if identity changed (caller may restart)."""
        changed_identity = False
        if doc.get("device_id"):
            nxt = self.normalize_device_id(doc["device_id"])
            if nxt and nxt != self.device_id:
                self.device_id = nxt
                changed_identity = True
        if doc.get("device_name"):
            self.device_name = str(doc["device_name"]).strip()
        key = doc.get("device_key") or doc.get("k")
        if key:
            self.device_key = str(key).strip()
        if doc.get("latitude") is not None:
            self.latitude = float(doc["latitude"])
        if doc.get("longitude") is not None:
            self.longitude = float(doc["longitude"])
        self.save()
        return changed_identity

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()
        self.device_id = "unassigned"
        self.device_key = ""
