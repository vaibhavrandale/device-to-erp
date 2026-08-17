#!/usr/bin/env python3
"""Generate SOP PDF for Taypro RasPi fingerprint attendance device."""

from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

OUT = Path(__file__).resolve().parent / "Taypro_Fingerprint_Device_SOP.pdf"


class SopPdf(FPDF):
    def _mc(self, h, text, **kwargs):
        """multi_cell that always returns to left margin (fpdf2 default leaves x at right)."""
        kwargs.setdefault("new_x", XPos.LMARGIN)
        kwargs.setdefault("new_y", YPos.NEXT)
        self.multi_cell(0, h, text, **kwargs)

    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, "Taypro Fingerprint Attendance Device - SOP", align="L")
        self.ln(4)
        self.set_draw_color(180, 180, 180)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(6)
        self.set_text_color(0, 0, 0)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}  |  Confidential - Taypro", align="C")

    def h1(self, text):
        self.set_font("Helvetica", "B", 16)
        self.set_text_color(20, 60, 100)
        self._mc(9, text)
        self.ln(2)
        self.set_text_color(0, 0, 0)

    def h2(self, text):
        self.ln(2)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(30, 80, 120)
        self._mc(7, text)
        self.ln(1)
        self.set_text_color(0, 0, 0)

    def body(self, text):
        self.set_font("Helvetica", "", 10)
        self._mc(5.5, text)
        self.ln(1)

    def bullet(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_x(self.l_margin + 4)
        w = self.epw - 4
        self.multi_cell(w, 5.5, f"-  {text}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def step(self, n, text):
        self.set_font("Helvetica", "B", 10)
        self.write(5.5, f"Step {n}: ")
        self.set_font("Helvetica", "", 10)
        self.multi_cell(0, 5.5, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(0.5)

    def code(self, text):
        self.set_fill_color(245, 245, 245)
        self.set_font("Courier", "", 8.5)
        self.set_x(self.l_margin + 4)
        self.multi_cell(
            self.epw - 4, 4.5, text, fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT
        )
        self.ln(2)

    def table(self, headers, rows, col_w=None):
        if col_w is None:
            col_w = [190 / len(headers)] * len(headers)
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(30, 80, 120)
        self.set_text_color(255, 255, 255)
        for i, h in enumerate(headers):
            self.cell(col_w[i], 7, h, border=1, fill=True)
        self.ln()
        self.set_text_color(0, 0, 0)
        self.set_font("Helvetica", "", 8.5)
        fill = False
        for row in rows:
            self.set_fill_color(240, 246, 252) if fill else self.set_fill_color(255, 255, 255)
            # estimate height
            y0 = self.get_y()
            if y0 > 270:
                self.add_page()
                y0 = self.get_y()
            x0 = self.get_x()
            max_h = 7
            cells = []
            for i, cell in enumerate(row):
                cells.append(str(cell))
            # simple single-line rows
            for i, cell in enumerate(cells):
                self.cell(col_w[i], max_h, cell[:45], border=1, fill=True)
            self.ln()
            fill = not fill
        self.ln(2)


def build():
    pdf = SopPdf()
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # Cover
    pdf.ln(20)
    pdf.set_font("Helvetica", "B", 22)
    pdf.set_text_color(20, 60, 100)
    pdf._mc(10, "STANDARD OPERATING PROCEDURE", align="C")
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 16)
    pdf._mc(8, "Taypro Fingerprint Attendance Device", align="C")
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(60, 60, 60)
    pdf._mc(7, "Raspberry Pi 3B + R307S + OLED + LEDs", align="C")
    pdf.ln(8)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 10)
    pdf._mc(
        6,
        "This document explains end-to-end how to configure the device, enroll employees, "
        "run daily attendance, and maintain the system at remote sites.",
        align="C",
    )
    pdf.ln(10)
    pdf.set_font("Helvetica", "", 10)
    pdf._mc(6, "Audience: Site technicians, HR admins, IT support", align="C")
    pdf._mc(6, "System: device-to-erp (Pi) + taypro-console (HR)", align="C")

    # 1 Purpose
    pdf.add_page()
    pdf.h1("1. Purpose & overview")
    pdf.body(
        "The fingerprint attendance device replaces RFID card tapping with fingerprint "
        "scans. When an enrolled finger is placed on the R307S sensor, the device sends "
        "a punch to the Taypro cloud over MQTT. The OLED shows status for remote sites "
        "(no monitor required). HR manages employees and enrollment from the console."
    )
    pdf.h2("1.1 What the device does")
    pdf.bullet("Connects to office Wi-Fi / Ethernet and MQTT cloud")
    pdf.bullet("Registers itself to HR as an attendance device")
    pdf.bullet("Matches finger templates stored on the R307S sensor")
    pdf.bullet("Publishes check-in / check-out punches to the server")
    pdf.bullet("Shows results on OLED + 3 status LEDs")
    pdf.bullet("Supports remote enroll from HR Admin UI (2 fingers per user)")

    pdf.h2("1.2 Important storage rule")
    pdf.body(
        "Fingerprint biometric templates live ON the R307S sensor chip (up to 1000). "
        "MongoDB / HR only stores mapping IDs like FP0001 and FP0002 on the employee record. "
        "If you replace the sensor hardware, users must be re-enrolled."
    )

    # 2 Hardware
    pdf.h1("2. Hardware bill of materials")
    pdf.table(
        ["Item", "Role"],
        [
            ["Raspberry Pi 3 Model B", "Runs attendance software"],
            ["R307 / R307S fingerprint sensor", "Scan & store templates"],
            ["CP2102 USB-UART converter", "Sensor serial link"],
            ['1.3" I2C OLED (SH1106/SSD1306)', "On-site display"],
            ["3x LEDs + 220 ohm resistors", "Net / OK / Fail status"],
            ["5V power for Pi + sensor VCC", "Stable power (sensor needs 5V)"],
        ],
        [70, 120],
    )

    pdf.h2("2.1 Wiring - fingerprint (CP2102)")
    pdf.table(
        ["R307S", "Connect to"],
        [
            ["VCC", "Pi 5V (physical pin 2) - NOT CP2102 3.3V"],
            ["GND", "CP2102 GND and Pi GND"],
            ["TX", "CP2102 RXD"],
            ["RX", "CP2102 TXD"],
            ["CP2102 USB", "Pi USB port -> /dev/ttyUSB0"],
        ],
        [50, 140],
    )
    pdf.body(
        "If the sensor LED flashes then dies on 3.3V, that is power collapse. Always use Pi 5V for VCC."
    )

    pdf.h2("2.2 Wiring - OLED (I2C)")
    pdf.table(
        ["OLED", "Pi pin"],
        [
            ["VCC", "Pin 1 (3.3V)"],
            ["GND", "Pin 6 (GND)"],
            ["SCL", "Pin 5 (GPIO3)"],
            ["SDA", "Pin 3 (GPIO2)"],
        ],
        [50, 140],
    )

    pdf.h2("2.3 Wiring - status LEDs")
    pdf.table(
        ["LED", "Meaning", "BCM GPIO", "Physical"],
        [
            ["1 Net", "Wi-Fi+MQTT OK / blink connecting", "17", "11"],
            ["2 OK", "Punch success (~3s)", "27", "13"],
            ["3 Fail", "Punch fail / not enrolled (~4s)", "22", "15"],
        ],
        [28, 78, 42, 42],
    )
    pdf.body("Each LED: GPIO -> 220 ohm -> LED anode -> LED cathode -> GND.")

    # 3 Software setup
    pdf.h1("3. First-time software setup (technician)")
    pdf.step(1, "Flash Raspberry Pi OS, create user (e.g. taypro), connect network.")
    pdf.step(2, "Enable Serial (UART) and I2C in raspi-config, then reboot.")
    pdf.code(
        "sudo raspi-config\n"
        "# Interface Options -> Serial: login shell No, hardware Yes\n"
        "# Interface Options -> I2C -> Enable\n"
        "sudo reboot"
    )
    pdf.step(3, "Clone the device repository and install Python deps.")
    pdf.code(
        "cd ~\n"
        "git clone https://github.com/<ORG>/device-to-erp.git\n"
        "cd device-to-erp\n"
        "python3 -m venv .venv\n"
        "source .venv/bin/activate\n"
        "pip install -r requirements.txt\n"
        "cp config.example.json config.json"
    )
    pdf.step(4, "Edit config.json (kept local, not overwritten by git pull).")
    pdf.code(
        '{\n'
        '  "mqtt_host": "<broker-host-or-ip>",\n'
        '  "mqtt_port": 1883,\n'
        '  "mqtt_username": "<user>",\n'
        '  "mqtt_password": "<pass>",\n'
        '  "fingerprint_port": "/dev/ttyUSB0",\n'
        '  "fingerprint_baud": 57600,\n'
        '  "oled_driver": "sh1106",\n'
        '  "led_net_pin": 17,\n'
        '  "led_ok_pin": 27,\n'
        '  "led_fail_pin": 22\n'
        "}"
    )
    pdf.step(5, "Verify sensor and OLED.")
    pdf.code(
        "ls -l /dev/ttyUSB0\n"
        "sudo i2cdetect -y 1          # expect 3c\n"
        "python3 diagnose.py\n"
        "python3 test_oled.py"
    )
    pdf.step(6, "Install auto-start service (pull + run on every reboot).")
    pdf.code("python3 scripts/install_service.py\nsudo reboot")

    # 4 HR config
    pdf.h1("4. HR console configuration")
    pdf.h2("4.1 Device in Attendance dashboard")
    pdf.bullet("Power on the Pi with network + MQTT working.")
    pdf.bullet("Device publishes register/heartbeat; it appears in HR Attendance devices.")
    pdf.bullet("Open the device -> set Name, Location, Latitude, Longitude.")
    pdf.bullet("Save & push config (lat/lng required or punches are refused).")
    pdf.bullet("Confirm device status shows Online.")

    pdf.h2("4.2 Employee setup (2 fingerprints recommended)")
    pdf.bullet("HR Admin -> Employees -> Add or Edit employee.")
    pdf.bullet("Select the online fingerprint reader.")
    pdf.bullet("Click Enroll Finger 1 -> place that finger twice when OLED says PLACE / REMOVE / PLACE AGAIN.")
    pdf.bullet("Click Enroll Finger 2 -> enroll a different finger the same way.")
    pdf.bullet("IDs auto-fill as FP0001 / FP0002 style values on the employee record.")
    pdf.bullet("Save the employee. Either finger can punch attendance.")

    pdf.body(
        "Do not use RFID Capture for this device. Enrollment is only via Enroll Finger buttons."
    )

    # 5 Daily operation
    pdf.h1("5. Daily operation (site users)")
    pdf.step(1, "Confirm OLED shows SCAN FINGER and top row W:OK   M:OK   L:OK.")
    pdf.step(2, "Place an enrolled finger firmly on the sensor.")
    pdf.step(3, "Wait for result:")
    pdf.bullet("OLED: CHECK IN or CHECK OUT + employee name")
    pdf.bullet("Green/OK LED briefly ON")
    pdf.step(4, "Lift finger before next punch. Holding the finger will not double-punch.")
    pdf.step(5, "If PLEASE WAIT / Finger ignored appears, wait a few seconds and try again.")

    pdf.h2("5.1 OLED meanings")
    pdf.table(
        ["Screen", "Meaning"],
        [
            ["SCAN FINGER", "Ready for attendance"],
            ["CHECK IN / CHECK OUT + name", "Punch accepted"],
            ["UNKNOWN FINGER", "Not in sensor memory - enroll needed"],
            ["NOT ENROLLED", "In sensor but not linked to HR employee"],
            ["PLACE / REMOVE FINGER", "Enrollment coaching"],
            ["PLEASE WAIT", "Cooldown - too soon after last punch"],
        ],
        [70, 120],
    )

    pdf.h2("5.2 LED meanings")
    pdf.table(
        ["LED", "On / Blink"],
        [
            ["Net", "Solid = cloud OK; Blink = connecting; Off = down"],
            ["OK", "Successful punch"],
            ["Fail", "Fail, reject, unknown finger, MQTT error"],
        ],
        [40, 150],
    )

    # 6 Updates
    pdf.h1("6. Software updates")
    pdf.body(
        "Developers push code to GitHub from the laptop. On site you only reboot the Pi. "
        "On boot, boot_run.py does git reset to origin/main, installs deps, and starts main.py."
    )
    pdf.code("# After developers push:\nsudo reboot")
    pdf.body(
        "config.json and data/ are gitignored and survive updates. "
        "Do not edit application code permanently on the Pi."
    )

    # 7 Maintenance
    pdf.h1("7. Maintenance & admin tools")
    pdf.h2("7.1 Flush all fingerprints on sensor")
    pdf.body("Wipes every template on the R307. HR FP IDs remain - re-enroll after.")
    pdf.code("source .venv/bin/activate\npython3 flush_all_fingerprints.py\n# type YES")

    pdf.h2("7.2 Device logs")
    pdf.body(
        "The device sends logs to the cloud (same MQTT a:log path as ESP). "
        "View them in HR Attendance -> device logs for this device."
    )

    pdf.h2("7.3 Service logs on Pi")
    pdf.code(
        "systemctl status taypro-fingerprint\n"
        "journalctl -u taypro-fingerprint -f\n"
        "tail -f ~/device-to-erp/data/boot_run.log"
    )

    # 8 Troubleshooting
    pdf.h1("8. Troubleshooting")
    pdf.table(
        ["Symptom", "Check / Fix"],
        [
            ["Sensor timeout / no header", "5V VCC, TX/RX swap, /dev/ttyUSB0"],
            ["OLED blank", "I2C enabled, i2cdetect 0x3C, try ssd1306"],
            ["W/M not OK", "Network + MQTT host; device online in HR"],
            ["NO LOCATION", "Set lat/lng on device in HR and push"],
            ["NOT ENROLLED", "Enroll Finger 1/2 for that employee"],
            ["UNKNOWN FINGER", "Finger not on this sensor - enroll"],
            ["Double punch", "Update code; lift finger between punches"],
            ["Logs empty in HR", "Device must be registered (id+key)"],
        ],
        [55, 135],
    )

    # 9 Checklist
    pdf.h1("9. Go-live checklist")
    pdf.bullet("Hardware wired (sensor 5V, OLED I2C, 3 LEDs)")
    pdf.bullet("Serial + I2C enabled; diagnose.py OK")
    pdf.bullet("config.json MQTT + /dev/ttyUSB0 correct")
    pdf.bullet("systemd service installed; survives reboot")
    pdf.bullet("Device online in HR; lat/lng set")
    pdf.bullet("Test employee enrolled with 2 fingers")
    pdf.bullet("Test check-in and check-out on OLED + LEDs")
    pdf.bullet("Device logs visible in HR after a punch")

    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 9)
    pdf.multi_cell(
        0,
        5,
        "End of SOP. For firmware questions see device-to-erp/README.md. "
        "For HR console see taypro-console-frontend / taypro-console-backend.",
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUT))
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build()
