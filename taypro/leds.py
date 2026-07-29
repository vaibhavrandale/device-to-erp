"""3 status LEDs for remote RasPi fingerprint reader.

LED 1 — network: WiFi+MQTT OK (solid) / connecting (blink) / down (off)
LED 2 — punch success (pulse)
LED 3 — punch fail / not enrolled (pulse)

Default BCM pins (change in config.json):
  net=17  ok=27  fail=22
  Physical: 11, 13, 15  (+ GND to LED cathodes via ~220Ω)
"""

from __future__ import annotations

import time
from typing import Any, Optional

# Optional on non-Pi desks
try:
    import RPi.GPIO as GPIO  # type: ignore

    _HAS_GPIO = True
except Exception:
    GPIO = None  # type: ignore
    _HAS_GPIO = False


class StatusLeds:
    def __init__(
        self,
        net_pin: int = 17,
        ok_pin: int = 27,
        fail_pin: int = 22,
        active_high: bool = True,
        ok_ms: float = 3000,
        fail_ms: float = 4000,
        enabled: bool = True,
    ):
        self.enabled = bool(enabled) and _HAS_GPIO
        self.net_pin = int(net_pin)
        self.ok_pin = int(ok_pin)
        self.fail_pin = int(fail_pin)
        self.active_high = bool(active_high)
        self.ok_ms = float(ok_ms)
        self.fail_ms = float(fail_ms)
        self._ok_until = 0.0
        self._fail_until = 0.0
        self._ready = False

        if not enabled:
            print("LEDs disabled in config")
            return
        if not _HAS_GPIO:
            print("[LED] RPi.GPIO not available — LEDs skipped")
            return

        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setwarnings(False)
            for pin in (self.net_pin, self.ok_pin, self.fail_pin):
                GPIO.setup(pin, GPIO.OUT)
                self._write(pin, False)
            self._ready = True
            print(
                f"LEDs OK net=BCM{self.net_pin} ok=BCM{self.ok_pin} fail=BCM{self.fail_pin}"
            )
        except Exception as exc:
            print(f"[LED] init failed: {exc}")
            self._ready = False

    def _write(self, pin: int, on: bool) -> None:
        if not self._ready:
            return
        level = on if self.active_high else (not on)
        GPIO.output(pin, GPIO.HIGH if level else GPIO.LOW)

    def trigger_ok(self, duration_s: float | None = None) -> None:
        ms = (duration_s * 1000) if duration_s is not None else self.ok_ms
        until = time.monotonic() + (ms / 1000.0)
        if until > self._ok_until:
            self._ok_until = until
        # clear fail pulse if success wins
        self._fail_until = 0.0

    def trigger_fail(self, duration_s: float | None = None) -> None:
        ms = (duration_s * 1000) if duration_s is not None else self.fail_ms
        until = time.monotonic() + (ms / 1000.0)
        if until > self._fail_until:
            self._fail_until = until

    def update(self, *, mqtt_ok: bool, connecting: bool = False) -> None:
        """Call from main loop."""
        if not self._ready:
            return
        now = time.monotonic()

        # LED1 — cloud link
        if mqtt_ok:
            net_on = True
        elif connecting:
            net_on = int(now * 2) % 2 == 0  # ~2Hz blink
        else:
            net_on = False
        self._write(self.net_pin, net_on)

        # LED2 — punch OK pulse
        self._write(self.ok_pin, now < self._ok_until)

        # LED3 — punch fail pulse
        self._write(self.fail_pin, now < self._fail_until)

    def off_all(self) -> None:
        if not self._ready:
            return
        for pin in (self.net_pin, self.ok_pin, self.fail_pin):
            self._write(pin, False)

    def close(self) -> None:
        self.off_all()
        if self._ready and _HAS_GPIO:
            try:
                GPIO.cleanup([self.net_pin, self.ok_pin, self.fail_pin])
            except Exception:
                pass
        self._ready = False


def create_leds(cfg: dict[str, Any]) -> Optional[StatusLeds]:
    if cfg.get("led_enabled") is False:
        return StatusLeds(enabled=False)
    return StatusLeds(
        net_pin=int(cfg.get("led_net_pin") or 17),
        ok_pin=int(cfg.get("led_ok_pin") or 27),
        fail_pin=int(cfg.get("led_fail_pin") or 22),
        active_high=bool(cfg.get("led_active_high", True)),
        ok_ms=float(cfg.get("led_ok_ms") or 3000),
        fail_ms=float(cfg.get("led_fail_ms") or 4000),
        enabled=True,
    )
