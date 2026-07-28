"""OLED UI mirrored from ESP8266 DeviceOled.h (1.3\" I2C SH1106/SSD1306)."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

from .storage import DeviceStorage, hardware_id

WIDTH = 128
HEIGHT = 64
TAP_SCREEN_S = 3.0
ERROR_SCREEN_S = 6.0


class OledDisplay:
    def __init__(
        self,
        driver: str = "sh1106",
        address: int = 0x3C,
        i2c_port: int = 1,
        width: int = WIDTH,
        height: int = HEIGHT,
        tap_screen_s: float = TAP_SCREEN_S,
        error_screen_s: float = ERROR_SCREEN_S,
    ):
        self.ready = False
        self.device = None
        self.width = width
        self.height = height
        self.tap_screen_s = tap_screen_s
        self.error_screen_s = error_screen_s
        self.showing_tap = False
        self.tap_until = 0.0
        self._font = None
        self._font_lg = None

        try:
            from luma.core.interface.serial import i2c
            from luma.oled.device import sh1106, ssd1306
            from PIL import ImageFont
        except ImportError as exc:
            print(f"[ERR-101] OLED libs missing: {exc} — pip install luma.oled pillow")
            return

        try:
            serial = i2c(port=i2c_port, address=address)
            drv = (driver or "sh1106").lower()
            if drv == "ssd1306":
                self.device = ssd1306(serial, width=width, height=height)
            else:
                self.device = sh1106(serial, width=width, height=height)
            self._font = ImageFont.load_default()
            try:
                self._font_lg = ImageFont.truetype(
                    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14
                )
            except OSError:
                self._font_lg = self._font
            self.ready = True
            print(f"OLED OK {drv} @ 0x{address:02x}")
        except Exception as exc:
            print(f"[ERR-101] OLED not found: {exc}")
            self.device = None
            self.ready = False

    def _canvas(self):
        from luma.core.render import canvas

        return canvas(self.device)

    def _text_size(self, draw, text: str, font) -> tuple[int, int]:
        if hasattr(draw, "textbbox"):
            box = draw.textbbox((0, 0), text, font=font)
            return box[2] - box[0], box[3] - box[1]
        return draw.textsize(text, font=font)

    def _centered(self, draw, text: str, y: int, font=None) -> None:
        font = font or self._font
        w, _ = self._text_size(draw, text, font)
        x = max(0, (self.width - w) // 2)
        draw.text((x, y), text, font=font, fill=1)

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        text = text or ""
        if len(text) <= max_len:
            return text
        if max_len <= 3:
            return text[:max_len]
        return text[: max_len - 3] + "..."

    @staticmethod
    def _punch_label(punch_type: str) -> str:
        return (punch_type or "").replace("_", " ").upper()

    def _mark_temp(self, seconds: float) -> None:
        self.showing_tap = True
        self.tap_until = time.monotonic() + seconds

    def poll_clear_temp(self, storage: DeviceStorage, mqtt_ok: bool) -> None:
        if self.showing_tap and time.monotonic() >= self.tap_until:
            self.showing_tap = False
            self.show_ready(storage, wifi_ok=True, mqtt_ok=mqtt_ok)

    def show_splash(self) -> None:
        if not self.ready:
            return
        with self._canvas() as draw:
            self._centered(draw, "TAYPRO", 24, self._font_lg)

    def show_lines(self, line1: str, line2: str = "", line3: str = "") -> None:
        if not self.ready:
            return
        with self._canvas() as draw:
            draw.text((0, 0), line1[:21], font=self._font, fill=1)
            if line2:
                draw.text((0, 12), line2[:21], font=self._font, fill=1)
            if line3:
                draw.text((0, 24), line3[:21], font=self._font, fill=1)

    def show_boot(self, wifi: str, cloud: str, reg: str, status: str = "") -> None:
        """wifi/cloud/reg: OK | -- | .."""
        if not self.ready:
            return
        with self._canvas() as draw:
            self._centered(draw, "TAYPRO ATTENDANCE", 0)
            draw.line((0, 10, self.width - 1, 10), fill=1)
            draw.text((0, 16), f"[{wifi}] Network", font=self._font, fill=1)
            draw.text((0, 28), f"[{cloud}] Cloud MQTT", font=self._font, fill=1)
            draw.text((0, 40), f"[{reg}] Register", font=self._font, fill=1)
            draw.line((0, 52, self.width - 1, 52), fill=1)
            self._centered(draw, self._truncate(status, 21), 54)

    def show_register_result(self, created: bool, device_id: str, message: str = "") -> None:
        if not self.ready:
            return
        title = "DEVICE CREATED" if created else "DEVICE LINKED"
        with self._canvas() as draw:
            self._centered(draw, title, 4)
            draw.line((0, 14, self.width - 1, 14), fill=1)
            draw.text((0, 20), self._truncate(message or title, 21), font=self._font, fill=1)
            self._centered(draw, self._truncate(device_id, 18), 54)
        self._mark_temp(2.5)

    def show_ready(self, storage: DeviceStorage, wifi_ok: bool = True, mqtt_ok: bool = True) -> None:
        if not self.ready or self.showing_tap:
            return
        wifi = "OK" if wifi_ok else "--"
        cloud = "OK" if mqtt_ok else "--"
        clock = datetime.now().strftime("%H:%M")
        ident = storage.device_id if storage.is_registered() else f"HW-{hardware_id()[-6:]}"
        with self._canvas() as draw:
            draw.text((18, 0), f"W:{wifi}", font=self._font, fill=1)
            draw.text((82, 0), f"M:{cloud}", font=self._font, fill=1)
            draw.line((0, 11, self.width - 1, 11), fill=1)
            self._centered(draw, clock, 14, self._font_lg)
            # TAP NOW pill
            draw.rectangle((16, 34, self.width - 16, 48), outline=1, fill=0)
            self._centered(draw, "SCAN NOW", 36)
            self._centered(draw, self._truncate(ident, 18), 52)

    def show_processing(self, card_id: str) -> None:
        self.show_lines("Processing", f"ID {card_id}", "Sending...")
        self._mark_temp(self.tap_screen_s)

    def show_tap_ok(self, employee_name: str, punch_type: str) -> None:
        if not self.ready:
            return
        self._mark_temp(self.tap_screen_s)
        name = employee_name or "-"
        punch = self._punch_label(punch_type) or "OK"
        # split name roughly like ESP
        max_chars = 10
        if len(name) <= max_chars:
            n1, n2 = name, ""
        else:
            break_at = name.rfind(" ", 0, max_chars)
            if break_at < 3:
                break_at = max_chars
            n1, n2 = name[:break_at], name[break_at:].strip()
            n2 = self._truncate(n2, max_chars)
        with self._canvas() as draw:
            y = 10
            self._centered(draw, n1, y, self._font_lg)
            if n2:
                self._centered(draw, n2, y + 16, self._font_lg)
                y = 42
            else:
                y = 36
            self._centered(draw, punch, y)

    def show_error(self, code: int, title: str, detail: str, extra: str = "") -> None:
        if not self.ready:
            return
        self._mark_temp(self.error_screen_s)
        with self._canvas() as draw:
            self._centered(draw, title or "ERROR", 0)
            draw.line((0, 10, self.width - 1, 10), fill=1)
            draw.text((0, 14), self._truncate(f"[{code}] {detail}", 21), font=self._font, fill=1)
            if len(detail) > 18:
                draw.text((0, 26), self._truncate(detail[18:], 21), font=self._font, fill=1)
            if extra:
                draw.line((0, 54, self.width - 1, 54), fill=1)
                self._centered(draw, self._truncate(extra, 21), 56)

    def show_no_match(self) -> None:
        self.show_error(704, "NO MATCH", "Finger not enrolled", "enroll.py --id N")


def create_oled(cfg: dict) -> Optional[OledDisplay]:
    if cfg.get("oled_enabled") is False:
        return None
    addr = cfg.get("oled_address", "0x3C")
    if isinstance(addr, str):
        address = int(addr, 16) if addr.lower().startswith("0x") else int(addr)
    else:
        address = int(addr)
    return OledDisplay(
        driver=str(cfg.get("oled_driver") or "sh1106"),
        address=address,
        i2c_port=int(cfg.get("oled_i2c_port") or 1),
        width=int(cfg.get("oled_width") or 128),
        height=int(cfg.get("oled_height") or 64),
        tap_screen_s=float(cfg.get("tap_screen_s") or TAP_SCREEN_S),
        error_screen_s=float(cfg.get("error_screen_s") or ERROR_SCREEN_S),
    )
