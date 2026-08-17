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
    "mqtt_username": "",
    "mqtt_password": "",
    "mqtt_tls": False,
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
    "tap_screen_s": 5,
    "error_screen_s": 8,
    "led_enabled": True,
    "led_net_pin": 17,
    "led_ok_pin": 27,
    "led_fail_pin": 22,
    "led_active_high": True,
    "led_ok_ms": 3000,
    "led_fail_ms": 4000,
    "log_sync_interval_s": 10,
    "heartbeat_interval_s": 120,
    "tap_response_timeout_s": 12,
    "register_timeout_s": 15,
    "finger_debounce_s": 10,
    "scan_poll_s": 0.2,
}


# Schemes that mean "wrap the connection in TLS". mqtt+ssl is the form Amazon MQ
# publishes, e.g. mqtt+ssl://b-xxxx-1.mq.ap-south-1.amazonaws.com:8883
TLS_SCHEMES = ("mqtts", "mqtt+ssl", "ssl", "tls")


def normalize_broker(cfg: dict[str, Any]) -> dict[str, Any]:
    """Accept mqtt_host as bare host, host:port, or <scheme>://host:port and split
    out host / port / TLS so paho.connect(host, port) always gets a clean host."""
    raw = str(cfg.get("mqtt_host") or "").strip()
    if "://" in raw:
        scheme, raw = raw.split("://", 1)
        if scheme.lower() in TLS_SCHEMES:
            cfg["mqtt_tls"] = True
    raw = raw.rstrip("/")

    # host:port (guard IPv6, which uses many colons)
    if raw.count(":") == 1:
        host, _, port = raw.partition(":")
        if port.isdigit():
            cfg["mqtt_host"] = host
            cfg["mqtt_port"] = int(port)
            return cfg

    cfg["mqtt_host"] = raw
    # TLS with no explicit port: 1883 is the plaintext default and would just hang,
    # so fall back to the conventional MQTT-over-TLS port instead.
    if cfg.get("mqtt_tls") and int(cfg.get("mqtt_port") or 1883) == 1883:
        cfg["mqtt_port"] = 8883
    return cfg


def load_config(path: Path | None = None) -> dict[str, Any]:
    cfg = deepcopy(DEFAULTS)
    cfg_path = path or CONFIG_PATH
    if cfg_path.exists():
        with cfg_path.open("r", encoding="utf-8") as f:
            file_cfg = json.load(f)
        if isinstance(file_cfg, dict):
            cfg.update(file_cfg)
    return normalize_broker(cfg)


def parse_u32(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, int):
        return value & 0xFFFFFFFF
    text = str(value).strip().lower()
    if text.startswith("0x"):
        return int(text, 16) & 0xFFFFFFFF
    return int(text) & 0xFFFFFFFF
