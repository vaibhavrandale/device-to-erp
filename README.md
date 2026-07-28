# Taypro RasPi 3B + R307S Fingerprint Attendance

Same MQTT attendance flow as `esp8266-attendance`, but fingerprint instead of RFID.

## Where fingerprint templates are stored

| Data | Where | Capacity |
|------|--------|----------|
| Biometric template | **On the R307S sensor flash** (not Pi disk, not MongoDB) | **1000** templates |
| Mapping id `FP0007` | HR user `rfid_card_id` in MongoDB | unlimited |

100+ users is fine (sensor holds 1000). If you replace the R307 module, re-enroll users (or keep the same sensor hardware).

### Two fingerprints per user

Each employee should enroll **2 fingers** (safety / injury backup):

| Slot | HR field | UI |
|------|----------|-----|
| Finger 1 | `rfid_card_id` | Enroll Finger 1 |
| Finger 2 | `rfid_card_id_2` | Enroll Finger 2 |

Both template ids live on the R307. Tap with **either** finger punches attendance.
100 users × 2 fingers = 200 templates (sensor holds 1000).

Edit always on the laptop in this folder. Never edit permanently on the Pi.

**Laptop (after any code change):**
```bash
cd C:\WebDevelopment\device-to-erp
git add -A
git commit -m "your message"
git push
```

**Raspberry Pi — only reboot** (auto git pull + start app):
```bash
sudo reboot
```

### One-time auto-boot setup on Pi
```bash
cd ~/attendance-erp/device-to-erp   # your clone path
git pull
python3 scripts/install_service.py
```

Service: `taypro-fingerprint` → runs `scripts/boot_run.py` which does
`git reset --hard origin/main`, installs deps, then starts `main.py`.

```bash
systemctl status taypro-fingerprint
journalctl -u taypro-fingerprint -f
tail -f data/boot_run.log
```

`config.json` / `data/` stay local (gitignored). Do not edit app code on the Pi.

First-time Pi clone (once):
```bash
cd ~
git clone https://github.com/YOUR_USER/device-to-erp.git
cd device-to-erp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
# edit config.json on Pi only (mqtt host, UART port) — this file is gitignored
```

`config.json` and `data/` stay local on each machine (not pushed).

| ESP8266 | RasPi 3B |
|---------|----------|
| RC522 RFID UID → `c` | R307S template id → `c` as `FP0001` |
| Arduino / PubSubClient | Python / paho-mqtt |
| WiFi STA on chip | Pi Ethernet/WiFi (OS network) |

## MQTT (unchanged)

| Direction | Topic |
|-----------|-------|
| Device → server | `hr/attendance/up` |
| Server → device | `hr/attendance/down/hw/{hardware_id}` |

Actions: `register`, `heartbeat`, `tap` — same JSON shape as ESP firmware.

Tap sends:

```json
{ "a": "tap", "hw": "...", "d": "...", "k": "...", "c": "FP0005", "latitude": 19.07, "longitude": 72.87 }
```

HR: put `FP0005` in the employee **RFID / card_id** field (same field as ESP cards).

## Wiring diagram (Pi 3B + CP2102 R307S + 1.3\" I2C OLED)

```text
                    Raspberry Pi 3 Model B
                 ┌─────────────────────────┐
                 │  Pin1  3.3V ──────────────┼── OLED VCC
                 │  Pin2  5V   ──────────────┼── R307 VCC
                 │  Pin3  GPIO2 SDA ─────────┼── OLED SDA
                 │  Pin5  GPIO3 SCL ─────────┼── OLED SCL
                 │  Pin6  GND  ──┬───────────┼── OLED GND
                 │               │           │
                 │  USB ─────────┼───────────┼── CP2102 USB
                 └───────────────┼───────────┘
                                 │
                    CP2102       │         R307S
                 ┌───────────┐   │      ┌──────────┐
                 │ GND ──────┼───┴──────┤ GND      │
                 │ RXD ──────┼──────────┤ TX       │
                 │ TXD ──────┼──────────┤ RX       │
                 │ 3.3V (do not power R307 from here)
                 └───────────┘          └──────────┘

OLED 1.30" IIC V2.2 (4 pins): VCC / GND / SCL / SDA
```

### OLED pin table

| OLED 1.30\" IIC | Pi 3B |
|-----------------|-------|
| VCC | Pin 1 (3.3V) |
| GND | Pin 6 (GND) |
| SCL | Pin 5 (GPIO3) |
| SDA | Pin 3 (GPIO2) |

Enable I2C once:
```bash
sudo raspi-config
# Interface Options → I2C → Enable
sudo reboot
# check:
sudo i2cdetect -y 1
# expect 0x3C (or 0x3D)
```

If the screen stays blank, try in `config.json`:
```json
"oled_driver": "ssd1306"
```
(default is `sh1106`, same as ESP `OLED_IS_SH1106`)

## Wiring (RasPi 3 Model B ↔ R307S via CP2102)

| R307S | Connection |
|-------|------------|
| VCC | Pi **5V** (pin 2) |
| GND | CP2102 GND + Pi GND |
| TX | CP2102 RXD |
| RX | CP2102 TXD |
| CP2102 USB | Pi USB → `/dev/ttyUSB0` |

## Wiring (RasPi 3 Model B ↔ R307S)

R307S is **3.3V UART** (do not feed 5V into Pi GPIO).

| R307S | Pi 3B |
|-------|-------|
| VCC (3.3V) | Pin 1 (3.3V) — or 5V only if module has onboard regulator **and** TX is 3.3V-safe |
| GND | Pin 6 (GND) |
| TX | Pin 10 (GPIO15 / RXD) |
| RX | Pin 8 (GPIO14 / TXD) |
| Touch / Wake | optional, unused |

Enable UART on Pi:

```bash
sudo raspi-config
# Interface Options → Serial Port
#   login shell over serial: No
#   serial port hardware: Yes
sudo reboot
```

Default port in config: `/dev/serial0` (57600 baud).

USB-TTL adapter instead of GPIO UART: set `"fingerprint_port": "/dev/ttyUSB0"`.

## Setup

```bash
cd /home/pi/device-to-erp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
# edit mqtt_host if needed
```

## Enroll fingers (once per employee)

```bash
python3 enroll.py --id 5
# Place finger twice when prompted
# → register card_id FP0005 on that employee in HR
```

List / delete:

```bash
python3 enroll.py --list
python3 enroll.py --delete 5
```

## Run attendance

```bash
python3 main.py
```

Boot: MQTT connect → `a:register` → heartbeat every 2 min → scan loop.

Set device **latitude/longitude** from HR dashboard (same as ESP) or the device refuses taps.

## systemd (optional)

`/etc/systemd/system/taypro-fingerprint.service`:

```ini
[Unit]
Description=Taypro fingerprint attendance
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/device-to-erp
ExecStart=/home/pi/device-to-erp/.venv/bin/python /home/pi/device-to-erp/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable --now taypro-fingerprint
```

## File map

| File | Role |
|------|------|
| `main.py` | Boot + scan loop |
| `enroll.py` | Enroll / delete templates on R307S |
| `taypro/fingerprint.py` | R307 UART driver |
| `taypro/mqtt_client.py` | MQTT up/down (ESP-compatible) |
| `taypro/tap.py` | Debounce + tap wait |
| `taypro/storage.py` | `data/device.cfg` + hardware id |
| `config.json` | Broker + UART settings |

## Notes

- `hardware_id` comes from Pi CPU serial (12 hex chars), same topic shape as ESP MAC.
- Fingerprints live **on the R307S**. Enroll on this Pi before HR mapping works.
- No OLED/LED UI in this port — status is Serial/stdout (add later if needed).
