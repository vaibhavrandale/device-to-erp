"""OLED UI for remote RasPi fingerprint reader (no monitor on site)."""

from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

from .storage import DeviceStorage, hardware_id

WIDTH = 128
HEIGHT = 64
RESULT_SCREEN_S = 5.0
ERROR_SCREEN_S = 8.0


class OledDisplay:
    def __init__(
        self,
        driver: str = "sh1106",
        address: int = 0x3C,
        i2c_port: int = 1,
        width: int = WIDTH,
        height: int = HEIGHT,
        tap_screen_s: float = RESULT_SCREEN_S,
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
        self._status_ip = ""
        self._status_extra = ""

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

    def set_status_meta(self, *, ip: str = "", extra: str = "") -> None:
        self._status_ip = ip or ""
        self._status_extra = extra or ""

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

    def _wrap(self, text: str, width: int = 21, max_lines: int = 3) -> list[str]:
        text = (text or "").strip()
        if not text:
            return []
        words = text.split()
        lines: list[str] = []
        cur = ""
        for w in words:
            trial = f"{cur} {w}".strip()
            if len(trial) <= width:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = w if len(w) <= width else w[:width]
                if len(lines) >= max_lines:
                    break
        if cur and len(lines) < max_lines:
            lines.append(cur)
        return lines

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
            self._centered(draw, "TAYPRO", 12, self._font_lg)
            self._centered(draw, "FINGERPRINT", 34)
            self._centered(draw, "ATTENDANCE", 46)

    def show_lines(self, line1: str, line2: str = "", line3: str = "", line4: str = "") -> None:
        if not self.ready:
            return
        with self._canvas() as draw:
            draw.text((0, 0), line1[:21], font=self._font, fill=1)
            if line2:
                draw.text((0, 12), line2[:21], font=self._font, fill=1)
            if line3:
                draw.text((0, 24), line3[:21], font=self._font, fill=1)
            if line4:
                draw.text((0, 36), line4[:21], font=self._font, fill=1)

    def show_boot(
        self,
        wifi: str,
        cloud: str,
        reg: str,
        status: str = "",
        *,
        ip: str = "",
        device_id: str = "",
    ) -> None:
        if not self.ready:
            return
        with self._canvas() as draw:
            self._centered(draw, "BOOT", 0)
            draw.line((0, 10, self.width - 1, 10), fill=1)
            draw.text((0, 12), f"Net [{wifi}]  Mqtt [{cloud}]", font=self._font, fill=1)
            draw.text((0, 24), f"Reg [{reg}] {self._truncate(device_id, 12)}", font=self._font, fill=1)
            if ip:
                draw.text((0, 36), self._truncate(f"IP {ip}", 21), font=self._font, fill=1)
            draw.line((0, 48, self.width - 1, 48), fill=1)
            self._centered(draw, self._truncate(status, 21), 52)

    def show_register_result(self, created: bool, device_id: str, message: str = "") -> None:
        if not self.ready:
            return
        title = "CREATED" if created else "LINKED"
        with self._canvas() as draw:
            self._centered(draw, f"DEVICE {title}", 0)
            draw.line((0, 10, self.width - 1, 10), fill=1)
            for i, line in enumerate(self._wrap(message or title, 21, 3)):
                draw.text((0, 14 + i * 12), line, font=self._font, fill=1)
            self._centered(draw, self._truncate(device_id, 20), 54)
        self._mark_temp(3.0)

    def show_ready(
        self,
        storage: DeviceStorage,
        wifi_ok: bool = True,
        mqtt_ok: bool = True,
        *,
        templates: int | None = None,
    ) -> None:
        if not self.ready or self.showing_tap:
            return
        wifi = "OK" if wifi_ok else "--"
        cloud = "OK" if mqtt_ok else "--"
        clock = datetime.now().strftime("%H:%M:%S")
        ident = storage.device_id if storage.is_registered() else f"HW-{hardware_id()[-6:]}"
        loc = "LOC OK" if storage.has_location() else "NO LOC"
        ip = self._status_ip or "-"
        with self._canvas() as draw:
            draw.text((0, 0), f"W:{wifi} M:{cloud} {loc}", font=self._font, fill=1)
            draw.line((0, 10, self.width - 1, 10), fill=1)
            self._centered(draw, clock, 12, self._font_lg)
            draw.rectangle((10, 30, self.width - 10, 44), outline=1, fill=0)
            self._centered(draw, "SCAN FINGER", 32)
            draw.text((0, 46), self._truncate(ident, 21), font=self._font, fill=1)
            extra = self._status_extra
            if templates is not None:
                extra = f"FP:{templates} {extra}".strip()
            draw.text(
                (0, 56),
                self._truncate(f"{ip} {extra}".strip(), 21),
                font=self._font,
                fill=1,
            )

    def show_processing(self, fp_id: str) -> None:
        now = datetime.now().strftime("%H:%M:%S")
        self.show_lines("MATCHED", fp_id, "Sending punch...", now)
        self._mark_temp(self.tap_screen_s)

    def show_punch_ok(
        self,
        employee_name: str,
        punch_type: str,
        *,
        fp_id: str = "",
        message: str = "",
        employee_id: str = "",
    ) -> None:
        if not self.ready:
            return
        self._mark_temp(self.tap_screen_s)
        punch = self._punch_label(punch_type) or "OK"
        name = employee_name or "-"
        now = datetime.now().strftime("%H:%M:%S")
        with self._canvas() as draw:
            self._centered(draw, punch, 0, self._font_lg)
            draw.line((0, 16, self.width - 1, 16), fill=1)
            for i, line in enumerate(self._wrap(name, 16, 2)):
                self._centered(draw, line, 18 + i * 12, self._font_lg if i == 0 else self._font)
            y = 42
            if employee_id:
                draw.text((0, y), self._truncate(employee_id, 21), font=self._font, fill=1)
                y = 52
            detail = " ".join(x for x in (fp_id, now) if x)
            if message and not employee_id:
                detail = self._truncate(message, 21)
            self._centered(draw, self._truncate(detail, 21), 54 if y == 42 else 54)

    # keep old name for callers
    def show_tap_ok(self, employee_name: str, punch_type: str, **kwargs) -> None:
        self.show_punch_ok(employee_name, punch_type, **kwargs)

    def show_error(self, code: int, title: str, detail: str, extra: str = "") -> None:
        if not self.ready:
            return
        self._mark_temp(self.error_screen_s)
        now = datetime.now().strftime("%H:%M:%S")
        with self._canvas() as draw:
            self._centered(draw, title or "ERROR", 0)
            draw.line((0, 10, self.width - 1, 10), fill=1)
            draw.text((0, 12), f"ERR {code}  {now}", font=self._font, fill=1)
            for i, line in enumerate(self._wrap(detail, 21, 3)):
                draw.text((0, 24 + i * 10), line, font=self._font, fill=1)
            if extra:
                draw.line((0, 54, self.width - 1, 54), fill=1)
                self._centered(draw, self._truncate(extra, 21), 56)

    def show_no_match(self) -> None:
        self.show_error(704, "NO MATCH", "Finger not in sensor. Enroll from HR UI.", "Finger 1 or 2")

    def show_enroll(self, finger: int, name: str, step: str) -> None:
        """Live enroll coach for remote OLED (no monitor)."""
        if not self.ready:
            return
        # Don't use temp timer — stay on this screen until next step
        self.showing_tap = True
        self.tap_until = time.monotonic() + 120.0
        title = f"ENROLL {finger}/2"
        name_line = self._truncate(name or "", 21)
        step_key = (step or "").lower()

        if step_key in ("place1", "place"):
            big, hint = "PLACE FINGER", "Scan 1 of 2 — press down"
        elif step_key == "got1":
            big, hint = "GOT IT!", "Hold still..."
        elif step_key in ("remove", "lift"):
            big, hint = "REMOVE FINGER", "Lift off the sensor"
        elif step_key == "place2":
            big, hint = "PLACE AGAIN", "Same finger — scan 2/2"
        elif step_key == "got2":
            big, hint = "GOT IT!", "Saving template..."
        elif step_key == "saving":
            big, hint = "SAVING...", "Please wait"
        else:
            big, hint = self._truncate(step, 14), ""

        with self._canvas() as draw:
            self._centered(draw, title, 0)
            draw.line((0, 10, self.width - 1, 10), fill=1)
            if name_line:
                self._centered(draw, name_line, 14)
            self._centered(draw, big, 28, self._font_lg)
            if hint:
                self._centered(draw, self._truncate(hint, 21), 50)


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
        tap_screen_s=float(cfg.get("tap_screen_s") or RESULT_SCREEN_S),
        error_screen_s=float(cfg.get("error_screen_s") or ERROR_SCREEN_S),
    )
