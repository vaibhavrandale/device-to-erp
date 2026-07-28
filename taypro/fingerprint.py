"""Minimal R307 / R307S UART driver (Adafruit fingerprint protocol)."""

from __future__ import annotations

import struct
import time
from typing import Optional

import serial

# Confirmation codes
OK = 0x00
NO_FINGER = 0x02
IMAGE_FAIL = 0x03
NO_MATCH = 0x09
PACKET_ACK = 0x07
CMD_GET_IMAGE = 0x01
CMD_IMAGE2TZ = 0x02
CMD_SEARCH = 0x04
CMD_REG_MODEL = 0x05
CMD_STORE = 0x06
CMD_DELETE = 0x0C
CMD_EMPTY = 0x0D
CMD_READ_SYS = 0x0F
CMD_HISPEED_SEARCH = 0x1B
CMD_PASSWORD = 0x13
CMD_TEMPLATE_COUNT = 0x1D


class FingerprintError(RuntimeError):
    pass


POWER_HINT = """
R307 LED on briefly then OFF = power collapse (not a code bug).

Wire like this with CP2102:
  R307 VCC  -> Raspberry Pi pin 2 (5V)     << not CP2102 3.3V
  R307 GND  -> CP2102 GND and Pi GND
  R307 TX   -> CP2102 RXD
  R307 RX   -> CP2102 TXD
  CP2102    -> Pi USB

LED must stay ON. Then: python3 diagnose.py
"""


class R307:
    def __init__(
        self,
        port: str = "/dev/ttyUSB0",
        baudrate: int = 57600,
        address: int = 0xFFFFFFFF,
        password: int = 0x00000000,
        timeout: float = 2.0,
        *,
        _ser: serial.Serial | None = None,
    ):
        self.address = address & 0xFFFFFFFF
        self.password = password & 0xFFFFFFFF
        self.ser = _ser or serial.Serial(port=port, baudrate=baudrate, timeout=timeout)
        time.sleep(0.3)
        self.ser.reset_input_buffer()
        if not self.verify_password():
            raise FingerprintError("R307 password verify failed — check wiring/port")

    @classmethod
    def open(
        cls,
        port: str,
        baudrate: int = 57600,
        address: int = 0xFFFFFFFF,
        password: int = 0x00000000,
        timeout: float = 2.0,
        try_bauds: tuple[int, ...] | None = None,
    ) -> "R307":
        """Open port; if preferred baud fails, try common R307 rates."""
        bauds: list[int] = []
        for b in (baudrate, *(try_bauds or (57600, 9600, 115200, 19200, 38400, 4800))):
            if b not in bauds:
                bauds.append(b)

        last_err: Exception | None = None
        for baud in bauds:
            ser = None
            try:
                ser = serial.Serial(port=port, baudrate=baud, timeout=timeout)
                time.sleep(0.3)
                ser.reset_input_buffer()
                sensor = cls(
                    port=port,
                    baudrate=baud,
                    address=address,
                    password=password,
                    timeout=timeout,
                    _ser=ser,
                )
                print(f"R307 linked OK on {port} @ {baud}")
                return sensor
            except Exception as exc:
                last_err = exc
                if ser is not None:
                    try:
                        ser.close()
                    except Exception:
                        pass
                print(f"  try {port} @ {baud}: {exc}")

        raise FingerprintError(
            f"No reply from R307 on {port}. Last error: {last_err}\n{POWER_HINT}"
        )
    def close(self) -> None:
        if self.ser and self.ser.is_open:
            self.ser.close()

    def __enter__(self) -> "R307":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    def _packet(self, pid: int, payload: bytes) -> bytes:
        length = len(payload) + 2
        header = struct.pack(">HIBH", 0xEF01, self.address, pid, length)
        chk = pid + (length >> 8) + (length & 0xFF) + sum(payload)
        return header + payload + struct.pack(">H", chk & 0xFFFF)

    def _write(self, pid: int, payload: bytes) -> None:
        self.ser.write(self._packet(pid, payload))

    def _read(self) -> tuple[int, bytes]:
        header = self.ser.read(9)
        if len(header) < 9:
            raise FingerprintError("R307 timeout waiting for header")
        start, addr, pid, length = struct.unpack(">HIBH", header)
        if start != 0xEF01:
            raise FingerprintError("R307 bad packet header")
        rest = self.ser.read(length)
        if len(rest) < length:
            raise FingerprintError("R307 short packet")
        payload = rest[:-2]
        return pid, payload

    def _command(self, code: int, data: bytes = b"") -> bytes:
        self._write(0x01, bytes([code]) + data)
        pid, payload = self._read()
        if pid != PACKET_ACK:
            raise FingerprintError(f"R307 unexpected pid=0x{pid:02x}")
        if not payload:
            raise FingerprintError("R307 empty ack")
        return payload

    def verify_password(self) -> bool:
        payload = self._command(CMD_PASSWORD, struct.pack(">I", self.password))
        return payload[0] == OK

    def read_sys_params(self) -> dict:
        payload = self._command(CMD_READ_SYS)
        if payload[0] != OK or len(payload) < 17:
            raise FingerprintError("R307 read sys params failed")
        # conf + status(2) sys_id(2) capacity(2) security(2) addr(4) packet(2) baud(2)
        _, status, sensor_type, capacity, security, addr, packet_size, baud = struct.unpack(
            ">BHHHHIHH", payload[:17]
        )
        return {
            "status": status,
            "sensor_type": sensor_type,
            "capacity": capacity,
            "security": security,
            "address": addr,
            "packet_size": packet_size,
            "baud": baud * 9600,
        }

    def template_count(self) -> int:
        payload = self._command(CMD_TEMPLATE_COUNT)
        if payload[0] != OK or len(payload) < 3:
            raise FingerprintError("R307 template count failed")
        return (payload[1] << 8) | payload[2]

    def get_image(self) -> int:
        return self._command(CMD_GET_IMAGE)[0]

    def image2tz(self, slot: int) -> int:
        return self._command(CMD_IMAGE2TZ, bytes([slot & 0xFF]))[0]

    def create_model(self) -> int:
        return self._command(CMD_REG_MODEL)[0]

    def store(self, location: int, slot: int = 1) -> int:
        return self._command(CMD_STORE, bytes([slot & 0xFF, (location >> 8) & 0xFF, location & 0xFF]))[0]

    def delete(self, location: int, count: int = 1) -> int:
        data = struct.pack(">HH", location & 0xFFFF, count & 0xFFFF)
        return self._command(CMD_DELETE, data)[0]

    def empty(self) -> int:
        return self._command(CMD_EMPTY)[0]

    def search(self, slot: int = 1, start: int = 0, count: int = 200) -> Optional[int]:
        data = struct.pack(">BHH", slot & 0xFF, start & 0xFFFF, count & 0xFFFF)
        payload = self._command(CMD_HISPEED_SEARCH, data)
        if payload[0] == NO_MATCH:
            return None
        if payload[0] != OK or len(payload) < 5:
            # fallback classic search
            payload = self._command(CMD_SEARCH, data)
            if payload[0] == NO_MATCH:
                return None
            if payload[0] != OK or len(payload) < 5:
                return None
        page_id = (payload[1] << 8) | payload[2]
        return page_id

    def wait_finger(self, present: bool = True, timeout_s: float = 30.0) -> bool:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            code = self.get_image()
            if present and code == OK:
                return True
            if not present and code == NO_FINGER:
                return True
            time.sleep(0.05)
        return False

    def capture_to_slot(self, slot: int, timeout_s: float = 30.0) -> None:
        if not self.wait_finger(True, timeout_s):
            raise FingerprintError("Timeout waiting for finger")
        code = self.get_image()
        if code != OK:
            raise FingerprintError(f"get_image failed code=0x{code:02x}")
        code = self.image2tz(slot)
        if code != OK:
            raise FingerprintError(f"image2tz({slot}) failed code=0x{code:02x}")

    def enroll(self, location: int, timeout_s: float = 30.0) -> int:
        """Two-scan enroll into sensor flash at page id `location`. Returns location."""
        print(f"Place finger for enroll #{location} (scan 1)...")
        self.capture_to_slot(1, timeout_s)
        print("Remove finger...")
        self.wait_finger(False, timeout_s)
        time.sleep(0.4)
        print("Place same finger again (scan 2)...")
        self.capture_to_slot(2, timeout_s)
        code = self.create_model()
        if code != OK:
            raise FingerprintError(f"create_model failed code=0x{code:02x}")
        code = self.store(location, slot=1)
        if code != OK:
            raise FingerprintError(f"store({location}) failed code=0x{code:02x}")
        return location

    def identify(self) -> Optional[int]:
        """One-shot: if finger present and matches, return template id."""
        code = self.get_image()
        if code == NO_FINGER:
            return None
        if code != OK:
            return None
        code = self.image2tz(1)
        if code != OK:
            return None
        return self.search(slot=1)


def finger_id_to_card(template_id: int) -> str:
    """Same field `c` as RFID UID — HR stores this as employee card_id."""
    return f"FP{template_id:04d}"
