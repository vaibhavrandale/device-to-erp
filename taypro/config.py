from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(os.environ.get("TAYPRO_CONFIG", ROOT / "config.json"))
DEVICE_CFG_PATH = Path(os.environ.get("TAYPRO_DEVICE_CFG", ROOT / "data" / "device.cfg"))

DEFAULTS: dict[str, Any] = {
    "mqtt_host": "52.66.177.182",
    "mqtt_port": 1883,
    "topic_up": "hr/attendance/up",
    "topic_down_hw_prefix": "hr/attendance/down/hw/",
    "device_id": "unassigned",
    "device_name": "Taypro Fingerprint",
    "device_key": "",
    "latitude": None,
    "longitude": None,
    "fingerprint_port": "/dev/ttyUSB0",
    "fingerprint_baud": 57600,
    "fingerprint_address": "0xFFFFFFFF",
    "fingerprint_password": "0x00000000",
    "oled_enabled": True,
    "oled_driver": "sh1106",
    "oled_address": "0x3C",
    "oled_i2c_port": 1,
    "oled_width": 128,
    "oled_height": 64,
    "tap_screen_s": 3,
    "error_screen_s": 6,
    "heartbeat_interval_s": 120,
    "tap_response_timeout_s": 12,
    "register_timeout_s": 15,
    "finger_debounce_s": 5,
    "scan_poll_s": 0.2,
}


def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg = deepcopy(DEFAULTS)
    cfg_path = path or CONFIG_PATH
    if cfg_path.exists():
        with cfg_path.open("r", encoding="utf-8") as f:
            file_cfg = json.load(f)
        if isinstance(file_cfg, dict):
            cfg.update(file_cfg)
    return cfg


def parse_u32(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, int):
        return value & 0xFFFFFFFF
    text = str(value).strip().lower()
    if text.startswith("0x"):
        return int(text, 16) & 0xFFFFFFFF
    return int(text) & 0xFFFFFFFF
