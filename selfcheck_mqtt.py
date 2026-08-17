#!/usr/bin/env python3
"""Self-check for MQTT auth + broker host normalization.

Run: python selfcheck_mqtt.py
Asserts config parsing/auth wiring, then attempts a real connect (best-effort).
"""
from __future__ import annotations

import sys

from taypro.config import DEFAULTS, load_config, normalize_broker
from taypro.mqtt_client import AttendanceMqtt
from taypro.storage import DeviceStorage


def check_normalization() -> None:
    # env-style paste: scheme + host + port must split cleanly
    got = normalize_broker({"mqtt_host": "mqtt://mqtt.chirpstack-prod.internal:1883"})
    assert got["mqtt_host"] == "mqtt.chirpstack-prod.internal", got["mqtt_host"]
    assert got["mqtt_port"] == 1883, got["mqtt_port"]
    # bare host with no port keeps default port
    got2 = normalize_broker({"mqtt_host": "broker.example", "mqtt_port": 1883})
    assert got2["mqtt_host"] == "broker.example" and got2["mqtt_port"] == 1883
    # mqtts scheme flags tls
    got3 = normalize_broker({"mqtt_host": "mqtts://h:8883"})
    assert got3["mqtt_port"] == 8883 and got3.get("mqtt_tls") is True
    print("[ok] broker normalization")


def check_auth_applied() -> None:
    cfg = load_config()
    assert cfg["mqtt_host"] == "mqtt.chirpstack-prod.internal", cfg["mqtt_host"]
    assert cfg["mqtt_username"] == "chirpstack", cfg["mqtt_username"]
    assert cfg["mqtt_password"], "password missing from config.json"
    storage = DeviceStorage(defaults=cfg)
    client = AttendanceMqtt(
        host=cfg["mqtt_host"],
        port=int(cfg["mqtt_port"]),
        topic_up=cfg["topic_up"],
        topic_down_prefix=cfg["topic_down_hw_prefix"],
        storage=storage,
        username=cfg["mqtt_username"],
        password=cfg["mqtt_password"],
    )
    # paho stores creds on the underlying client (1.x: _username, 2.x: _username bytes)
    uname = getattr(client.client, "_username", None)
    assert uname in ("chirpstack", b"chirpstack"), uname
    print("[ok] username/password applied to paho client")
    return cfg, storage


def try_connect(cfg, storage) -> None:
    client = AttendanceMqtt(
        host=cfg["mqtt_host"],
        port=int(cfg["mqtt_port"]),
        topic_up=cfg["topic_up"],
        topic_down_prefix=cfg["topic_down_hw_prefix"],
        storage=storage,
        username=cfg["mqtt_username"],
        password=cfg["mqtt_password"],
    )
    print(f"[..] connecting to {cfg['mqtt_host']}:{cfg['mqtt_port']} ...")
    ok = client.connect(timeout_s=8)
    client.disconnect()
    if ok:
        print("[ok] broker connected + authenticated")
    else:
        print("[warn] connect failed (expected off the prod network / internal DNS)")


if __name__ == "__main__":
    assert "mqtt_username" in DEFAULTS and "mqtt_password" in DEFAULTS
    check_normalization()
    cfg, storage = check_auth_applied()
    try:
        try_connect(cfg, storage)
    except Exception as exc:  # network is best-effort in this check
        print(f"[warn] connect raised: {exc}")
    print("SELF-CHECK PASSED (assertions ok)")
    sys.exit(0)
