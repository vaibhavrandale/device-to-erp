#!/usr/bin/env python3
"""Simple visual PDF: fingerprint device IN / OUT only.

Run from repo root or docs/:
  py docs/generate_inout_guide_pdf.py
"""

from pathlib import Path

from fpdf import FPDF
from fpdf.enums import XPos, YPos

OUT = Path(__file__).resolve().parent / "Fingerprint-Device-In-Out-Guide.pdf"


class GuidePdf(FPDF):
    def __init__(self):
        super().__init__(format="Letter")
        self.set_auto_page_break(auto=False)

    def header_bar(self, title: str, step: int, total: int):
        self.set_fill_color(26, 89, 184)
        self.rect(0, 0, 216, 28, style="F")
        self.set_xy(12, 6)
        self.set_font("Helvetica", "", 10)
        self.set_text_color(255, 255, 255)
        self.cell(0, 5, "Fingerprint Attendance Device")
        self.set_xy(12, 13)
        self.set_font("Helvetica", "B", 16)
        self.cell(140, 8, title)
        self.set_xy(180, 10)
        self.set_font("Helvetica", "B", 12)
        self.cell(24, 8, f"{step} / {total}", align="R")
        self.set_text_color(30, 35, 50)

    def footer_hint(self, text: str):
        self.set_xy(12, 270)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(120, 125, 140)
        self.cell(0, 6, text)
        self.set_text_color(30, 35, 50)

    def device_box(self, x, y, label, border_rgb, screen_rgb):
        self.set_fill_color(45, 50, 65)
        self.set_draw_color(*border_rgb)
        self.set_line_width(0.8)
        self.rect(x, y, 50, 70, style="DF")
        self.set_fill_color(*screen_rgb)
        self.rect(x + 6, y + 8, 38, 28, style="F")
        self.set_xy(x + 6, y + 16)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(255, 255, 255)
        self.cell(38, 8, label, align="C")
        # sensor
        self.set_fill_color(80, 85, 100)
        self.set_draw_color(240, 200, 160)
        self.ellipse(x + 15, y + 44, 20, 14, style="DF")
        self.set_xy(x + 6, y + 60)
        self.set_font("Helvetica", "B", 7)
        self.set_text_color(150, 155, 165)
        self.cell(38, 5, "SENSOR", align="C")
        self.set_text_color(30, 35, 50)
        self.set_line_width(0.2)

    def card(self, x, y, w, h, fill, border, title, subtitle, lines):
        self.set_fill_color(*fill)
        self.set_draw_color(*border)
        self.set_line_width(0.6)
        self.rect(x, y, w, h, style="DF")
        self.set_xy(x + 6, y + 8)
        self.set_font("Helvetica", "B", 28)
        self.set_text_color(*border)
        self.cell(w - 12, 12, title)
        self.set_xy(x + 6, y + 24)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(30, 35, 50)
        self.cell(w - 12, 8, subtitle)
        self.set_font("Helvetica", "", 11)
        yy = y + 38
        for line in lines:
            self.set_xy(x + 6, yy)
            self.cell(w - 12, 6, line)
            yy += 7


def build():
    pdf = GuidePdf()
    total = 6

    # 1 Overview
    pdf.add_page()
    pdf.set_fill_color(247, 249, 255)
    pdf.rect(0, 0, 216, 279, style="F")
    pdf.header_bar("How IN & OUT works", 1, total)
    pdf.set_xy(12, 40)
    pdf.set_font("Helvetica", "", 13)
    pdf.cell(0, 8, "Very simple. Two actions only:")
    pdf.card(
        12,
        55,
        90,
        55,
        (224, 245, 230),
        (20, 140, 80),
        "IN",
        "Check In",
        ["Put your finger when you", "START work."],
    )
    pdf.card(
        112,
        55,
        90,
        55,
        (255, 240, 224),
        (190, 115, 15),
        "OUT",
        "Check Out",
        ["Put your finger when you", "FINISH work."],
    )
    pdf.set_xy(12, 125)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(15, 55, 120)
    pdf.cell(0, 8, "Same finger. Same device. System decides IN or OUT.")
    pdf.set_xy(12, 136)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(100, 105, 120)
    pdf.cell(0, 7, "You do not press any IN / OUT button.")
    pdf.footer_hint("Flip to next page ->")

    # 2 Place finger
    pdf.add_page()
    pdf.set_fill_color(247, 249, 255)
    pdf.rect(0, 0, 216, 279, style="F")
    pdf.header_bar("Step 1 - Place finger", 2, total)
    pdf.set_xy(12, 40)
    pdf.set_font("Helvetica", "B", 14)
    pdf.set_text_color(30, 35, 50)
    pdf.cell(0, 8, "1. Stand at the device")
    pdf.set_xy(12, 50)
    pdf.cell(0, 8, "2. Place your enrolled finger on the sensor")
    pdf.device_box(83, 80, "READY", (26, 89, 184), (30, 115, 90))
    pdf.set_xy(12, 165)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(100, 105, 120)
    pdf.cell(0, 8, "Hold steady for 1-2 seconds.")
    pdf.footer_hint("Flip to next page ->")

    # 3 First punch IN
    pdf.add_page()
    pdf.set_fill_color(247, 249, 255)
    pdf.rect(0, 0, 216, 279, style="F")
    pdf.header_bar("Step 2 - First punch = IN", 3, total)
    pdf.set_fill_color(224, 245, 230)
    pdf.rect(12, 40, 190, 22, style="F")
    pdf.set_xy(16, 46)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(20, 140, 80)
    pdf.cell(0, 8, "First successful scan of the day  ->  CHECK IN")
    pdf.device_box(83, 80, "IN", (20, 140, 80), (20, 100, 60))
    pdf.set_xy(12, 165)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(30, 35, 50)
    pdf.cell(0, 8, "Screen shows you are IN (started work).")
    pdf.set_xy(12, 175)
    pdf.set_text_color(100, 105, 120)
    pdf.cell(0, 8, "Your attendance is saved on the server.")
    pdf.footer_hint("Flip to next page ->")

    # 4 Work
    pdf.add_page()
    pdf.set_fill_color(247, 249, 255)
    pdf.rect(0, 0, 216, 279, style="F")
    pdf.header_bar("Step 3 - Work as usual", 4, total)
    pdf.set_fill_color(255, 255, 255)
    pdf.set_draw_color(210, 215, 225)
    pdf.rect(30, 55, 155, 90, style="DF")
    pdf.set_xy(30, 75)
    pdf.set_font("Helvetica", "B", 24)
    pdf.set_text_color(20, 140, 80)
    pdf.cell(155, 12, "You are IN", align="C")
    pdf.set_xy(30, 95)
    pdf.set_font("Helvetica", "", 14)
    pdf.set_text_color(30, 35, 50)
    pdf.cell(155, 8, "Continue your work.", align="C")
    pdf.set_xy(30, 110)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(100, 105, 120)
    pdf.cell(155, 7, "No need to touch the device again", align="C")
    pdf.set_xy(30, 118)
    pdf.cell(155, 7, "until you leave.", align="C")
    pdf.footer_hint("Flip to next page ->")

    # 5 OUT
    pdf.add_page()
    pdf.set_fill_color(247, 249, 255)
    pdf.rect(0, 0, 216, 279, style="F")
    pdf.header_bar("Step 4 - Second punch = OUT", 5, total)
    pdf.set_fill_color(255, 240, 224)
    pdf.rect(12, 40, 190, 22, style="F")
    pdf.set_xy(16, 46)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(190, 115, 15)
    pdf.cell(0, 8, "Next successful scan  ->  CHECK OUT")
    pdf.device_box(83, 80, "OUT", (190, 115, 15), (120, 70, 20))
    pdf.set_xy(12, 165)
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(30, 35, 50)
    pdf.cell(0, 8, "Place the same finger again when you finish work.")
    pdf.set_xy(12, 175)
    pdf.set_text_color(100, 105, 120)
    pdf.cell(0, 8, "Screen shows you are OUT (ended work).")
    pdf.footer_hint("Flip to next page ->")

    # 6 Remember
    pdf.add_page()
    pdf.set_fill_color(247, 249, 255)
    pdf.rect(0, 0, 216, 279, style="F")
    pdf.header_bar("Remember", 6, total)
    tips = [
        "Same finger for IN and OUT",
        "First scan = IN   |   Next scan = OUT",
        "Hold finger steady on the sensor",
        "Wait for success message on screen",
        "Use the device at your site (office / factory)",
    ]
    y = 45
    for i, tip in enumerate(tips, 1):
        pdf.set_fill_color(26, 89, 184)
        pdf.ellipse(14, y, 8, 8, style="F")
        pdf.set_xy(14, y + 1.5)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(8, 5, str(i), align="C")
        pdf.set_xy(28, y + 1)
        pdf.set_font("Helvetica", "B", 13)
        pdf.set_text_color(30, 35, 50)
        pdf.cell(0, 7, tip)
        y += 18

    pdf.set_fill_color(230, 237, 250)
    pdf.rect(12, 160, 190, 20, style="F")
    pdf.set_xy(16, 166)
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(15, 55, 120)
    pdf.cell(0, 8, "That is all - IN when you start, OUT when you finish.")
    pdf.footer_hint("Taypro Attendance - Fingerprint Device Guide")

    pdf.output(OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    build()
