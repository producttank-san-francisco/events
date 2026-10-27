#!/usr/bin/env python3
"""Render three static comparison mockups; never rewrite the source GIF or stats.

Run from any directory: python3 -B /path/to/render_options.py
Requires Pillow and uses the existing slopegraph's palette and font loader.
"""
from __future__ import annotations

import json
import math
import sys
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "src/rsvp-slopegraph/src"))
from rsvp_slopegraph import (  # noqa: E402
    BACKGROUND, CLONES, MUTED, RENDER_SCALE, TEXT, VIEWS, load_font,
)

DATA = json.loads((ROOT / "docs/reports/rsvp-slopegraph/stats.json").read_text())
SEP, OCT = DATA["september"], DATA["october"]
S_TOTAL = SEP["named_guests"] + SEP["unnamed_plus_ones"]
O_TOTAL = OCT["named_guests"] + OCT["unnamed_plus_ones"]
S_EMAIL, O_EMAIL, ATTENDED = SEP["guests_with_email"], OCT["guests_with_email"], SEP["attended"]
S_SHARE, O_SHARE = Fraction(S_EMAIL, S_TOTAL), Fraction(O_EMAIL, O_TOTAL)
RATIO = Fraction(ATTENDED, S_EMAIL)
ESTIMATE = O_EMAIL * RATIO
ALTERNATE = O_TOTAL * Fraction(ATTENDED, S_TOTAL)
GAP = (S_SHARE - O_SHARE) * 100
W, H, SCALE = 1200, 1040, RENDER_SCALE
SEPT_COLOR, OCT_COLOR = CLONES, VIEWS
FONTS = {size: load_font(size) for size in (15, 17, 18, 20, 22, 24, 28, 32, 40)}
BOLD = {size: load_font(size, bold=True) for size in (18, 20, 22, 24, 28, 32, 40)}


def pct(value: Fraction) -> str:
    return f"{float(value) * 100:.1f}%"


class Canvas:
    def __init__(self, option: str, title: str, subtitle: str):
        self.image = Image.new("RGB", (W * SCALE, H * SCALE), BACKGROUND)
        self.draw = ImageDraw.Draw(self.image)
        self.text(64, 38, "ProductTank SF · September / October 2026", 18, MUTED)
        self.text(1136, 38, f"{option} · STATIC STUDY", 15, MUTED, anchor="ra")
        self.text(64, 91, title, 40, bold=True)
        self.text(64, 149, subtitle, 22, MUTED)

    def text(self, x, y, text, size=20, color=TEXT, *, bold=False, anchor="la"):
        font = (BOLD if bold else FONTS)[size]
        position = (x * SCALE, y * SCALE)
        box = self.draw.textbbox(position, text, font=font, anchor=anchor)
        if box[0] < 0 or box[1] < 0 or box[2] > W * SCALE or box[3] > H * SCALE:
            raise ValueError(f"Text outside canvas: {text!r}, {box}")
        self.draw.text(position, text, fill=color, font=font, anchor=anchor)

    def line(self, start, end, color=MUTED, width=1, dashed=False):
        if not dashed:
            self.draw.line(tuple(v * SCALE for point in (start, end) for v in point), fill=color, width=width * SCALE)
            return
        length = math.dist(start, end)
        for offset in range(0, math.ceil(length), 17):
            a, b = offset / length, min(offset + 9, length) / length
            self.line(tuple(p + (q-p)*a for p, q in zip(start, end)),
                      tuple(p + (q-p)*b for p, q in zip(start, end)), color, width)

    def dot(self, x, y, color, *, hollow=False, radius=5):
        bounds = tuple(v * SCALE for v in (x-radius, y-radius, x+radius, y+radius))
        self.draw.ellipse(bounds, fill=BACKGROUND if hollow else color, outline=color, width=2 * SCALE)

    def footer(self):
        self.text(64, 744, "Email-based estimate", 18, MUTED)
        self.text(64, 775, f"{O_EMAIL} × ({ATTENDED}/{S_EMAIL}) = {ESTIMATE} = {float(ESTIMATE):.10f}… → about {round(ESTIMATE)}", 28, OCT_COLOR, bold=True)
        self.text(64, 825, f"RSVP-based comparison: {O_TOTAL} × ({ATTENDED}/{S_TOTAL}) = {ALTERNATE} = {float(ALTERNATE):.10f}… → about {round(ALTERNATE)}", 20, MUTED)
        self.text(64, 861, "84 is a door head count, not verified attendance among the 136 email guests.", 18)
        self.text(64, 889, "84/136 is an aggregate ratio—not an email-guest conversion rate. October reuses it as an assumption.", 18, MUTED)
        as_of = datetime.fromisoformat(OCT["as_of"].replace("Z", "+00:00"))
        local = as_of.astimezone(ZoneInfo("America/Los_Angeles"))
        stamp = local.strftime("%b %-d, %Y · %-I:%M:%S %p %Z")
        self.text(64, 937, f"October snapshot: {stamp} ({as_of.strftime('%H:%M:%S UTC')}). Not a live count.", 17, MUTED)
        self.text(64, 964, f"RSVPs: September {SEP['named_guests']} named + {SEP['unnamed_plus_ones']} plus-ones; October {OCT['named_guests']} + {OCT['unnamed_plus_ones']}.", 17, MUTED)
        self.text(64, 991, "Later build notes report 133 named guests; this comparison deliberately retains the saved 132-row snapshot.", 17, MUTED)

    def save(self, name):
        self.footer()
        image = self.image.resize((W, H), Image.Resampling.LANCZOS)
        path = HERE / name
        image.save(path)
        print(f"Rendered {path.relative_to(ROOT)} ({W} × {H})")


def option_a():
    c = Canvas("A", "Similar proportional drops; about 49 attendees assumed.",
               "Follow each month across the counts. Only October’s attendance step is assumed.")
    xs = (260, 640, 1020)
    for x, label in zip(xs, ("RSVPs", "With email", "Attended")):
        c.text(x, 211, label, 22, anchor="ma", bold=True)
    def y(value):
        return 650 - math.log(float(value) / 40) / math.log(260 / 40) * 390
    for tick in (40, 80, 160):
        c.text(115, y(tick), str(tick), 17, MUTED, anchor="rm")
        c.line((126, y(tick)), (134, y(tick)))
    c.text(74, 239, "People", 17, MUTED)
    for name, counts, color in (("September", (S_TOTAL, S_EMAIL, ATTENDED), SEPT_COLOR),
                                 ("October", (O_TOTAL, O_EMAIL, ESTIMATE), OCT_COLOR)):
        ys = [y(v) for v in counts]
        c.text(xs[0]-16, ys[0]-24, f"{name} · {counts[0]}", 22, color, anchor="ra", bold=True)
        for i in range(2):
            c.line((xs[i], ys[i]), (xs[i+1], ys[i+1]), color, 3, dashed=name == "October" and i == 1)
        for i, (x, yy, value) in enumerate(zip(xs, ys, counts)):
            estimated = name == "October" and i == 2
            c.dot(x, yy, color, hollow=estimated)
            if i:
                label = f"{float(value):.1f} estimate" if estimated else str(value)
                c.text(x+13, yy-35, label, 22, color, bold=True)
        first_share = S_SHARE if name == "September" else O_SHARE
        c.text((xs[0]+xs[1])/2, (ys[0]+ys[1])/2-53, f"{pct(first_share)} retained", 20, color, anchor="ma")
        c.text((xs[1]+xs[2])/2, (ys[1]+ys[2])/2-53,
               f"{pct(RATIO)} {'assumed' if name == 'October' else 'ratio'}", 20, color, anchor="ma")
    c.text(64, 693, f"Log count scale: equal percentage drops have equal slopes. Email-share gap: {float(GAP):.4f}… points.", 18, MUTED)
    c.save("option-a-log-scale-three-stage-slopegraph.png")


def option_b():
    c = Canvas("B", "Email shares are close. Reuse September’s next ratio.",
               "Two steps, two identical 0–100% scales. October’s second dot is an assumption, not evidence.")
    for left, right, title, subtitle, ratios, labels in (
        (64, 550, "RSVPs → with email", "Similar, not identical", (S_SHARE, O_SHARE),
         (f"{S_EMAIL} / {S_TOTAL} RSVPs", f"{O_EMAIL} / {O_TOTAL} RSVPs")),
        (650, 1136, "With email → attended", "Aggregate ratio; not a tracked cohort", (RATIO, RATIO),
         (f"{ATTENDED} / {S_EMAIL} email guests", f"{float(ESTIMATE):.1f} estimated / {O_EMAIL} email guests")),
    ):
        c.text(left, 231, title, 28, bold=True)
        c.text(left, 275, subtitle, 18, MUTED)
        for row, (name, color, ratio, label) in enumerate(zip(("September", "October"), (SEPT_COLOR, OCT_COLOR), ratios, labels)):
            yy = 371 + row*143
            x = left + float(ratio)*(right-left)
            assumed = left == 650 and row == 1
            c.text(left, yy-43, name, 20, color, bold=True)
            c.dot(x, yy, color, hollow=assumed, radius=6)
            c.text(x+15, yy, pct(ratio), 28, color, anchor="lm", bold=True)
            c.text(left, yy+29, label + (" · assumed" if assumed else ""), 18, color)
        c.line((left, 599), (right, 599))
        for p in (0, .5, 1):
            x = left+p*(right-left)
            c.line((x, 594), (x, 604))
            c.text(x, 615, f"{p:.0%}", 17, MUTED, anchor="ma")
    c.text(64, 671, f"136/237 vs. 80/144 · gap {float(GAP):.4f}… percentage points", 18, MUTED)
    c.text(650, 671, "84/136 = 21/34 · same ratio assumed for October", 18, MUTED)
    c.save("option-b-step-ratio-small-multiples.png")


def option_c():
    c = Canvas("C", "The counts, the ratios, and the assumption—in one table.",
               "Read across each stage. Tiny bars share a zero baseline and a 0–250-person scale.")
    c.text(64, 229, "Stage", 20, MUTED)
    c.text(410, 229, "September", 24, SEPT_COLOR, bold=True)
    c.text(710, 229, "October", 24, OCT_COLOR, bold=True)
    c.text(990, 229, "October status", 20, MUTED)
    rows = (("RSVPs", S_TOTAL, O_TOTAL, "Observed snapshot"),
            ("With email", S_EMAIL, O_EMAIL, "Observed snapshot"),
            ("Attended", ATTENDED, ESTIMATE, "ASSUMED"))
    for i, (label, sv, ov, status) in enumerate(rows):
        yy = 310+i*98
        c.text(64, yy, label, 24)
        for x, value, color in ((410, sv, SEPT_COLOR), (710, ov, OCT_COLOR)):
            estimated = i == 2 and x == 710
            c.text(x, yy-4, f"≈{float(value):.1f}" if estimated else str(value), 32, color, bold=True)
            c.line((x, yy+46), (x+float(value)/250*220, yy+46), color, 4, dashed=estimated)
            c.line((x, yy+40), (x, yy+52), MUTED)
        c.text(990, yy+7, status, 18, OCT_COLOR if i == 2 else MUTED, bold=i == 2)
    c.text(64, 609, "With email / RSVPs", 20)
    c.text(410, 609, pct(S_SHARE), 24, SEPT_COLOR, bold=True)
    c.text(710, 609, pct(O_SHARE), 24, OCT_COLOR, bold=True)
    c.text(990, 613, f"Gap {float(GAP):.4f}… pt", 18, MUTED)
    c.text(64, 661, "Attended / with email", 20)
    c.text(410, 661, pct(RATIO), 24, SEPT_COLOR, bold=True)
    c.text(710, 661, pct(RATIO), 24, OCT_COLOR, bold=True)
    c.text(990, 665, "Same ratio assumed", 18, OCT_COLOR)
    c.save("option-c-counts-and-ratios-table-graphic.png")


if __name__ == "__main__":
    for render in (option_a, option_b, option_c):
        render()
    for label, value in (("September email share", S_SHARE), ("October email share", O_SHARE),
                         ("Gap (percentage points)", GAP), ("Attendance/email ratio", RATIO),
                         ("Email estimate", ESTIMATE), ("RSVP estimate", ALTERNATE),
                         ("Estimate difference", ALTERNATE-ESTIMATE)):
        print(f"{label}: {value} = {float(value):.12f}")
