#!/usr/bin/env python3
"""Render three comparison mockups and Option A's animated GIF; never rewrite the source GIF or stats.

Run from any directory: python3 -B /path/to/render_options.py
Requires Pillow and Gifski, and reuses the existing slopegraph's palette, font loader and animation timing.
"""
from __future__ import annotations

import json
import math
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT / "src/rsvp-slopegraph/src"))
from rsvp_slopegraph import (  # noqa: E402
    BACKGROUND, CLONES, FINAL_HOLD_FRAMES, FPS, LABEL_FADE, MOTION_STEPS, MUTED, OPENING_HOLD_FRAMES,
    RENDER_SCALE, STAGGER, TEXT, VIEWS, AnimationError, fade, line_progress, load_font, segment_hits_box,
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
FONTS = {size: load_font(size) for size in (15, 16, 17, 18, 20, 22, 24, 28, 32, 40)}
BOLD = {size: load_font(size, bold=True) for size in (18, 20, 22, 24, 28, 32, 40)}


def pct(value: Fraction) -> str:
    return f"{float(value) * 100:.1f}%"


class Canvas:
    def __init__(self, option="", title="", subtitle="", *, width=W, height=H):
        self.width, self.height = width, height
        self.image = Image.new("RGB", (width * SCALE, height * SCALE), BACKGROUND)
        self.draw = ImageDraw.Draw(self.image)
        if option:
            self.text(64, 38, "ProductTank SF · September / October 2026", 18, MUTED)
            self.text(1136, 38, f"{option} · STATIC STUDY", 15, MUTED, anchor="ra")
            self.text(64, 91, title, 40, bold=True)
            self.text(64, 149, subtitle, 22, MUTED)

    def text(self, x, y, text, size=20, color=TEXT, *, bold=False, anchor="la"):
        font = (BOLD if bold else FONTS)[size]
        position = (x * SCALE, y * SCALE)
        box = self.draw.textbbox(position, text, font=font, anchor=anchor)
        if box[0] < 0 or box[1] < 0 or box[2] > self.width * SCALE or box[3] > self.height * SCALE:
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
        self.text(64, 744, "Email-based estimate (current main)", 18, MUTED)
        self.text(64, 775, f"{O_EMAIL} × ({ATTENDED}/{S_EMAIL}) = {ESTIMATE} = {float(ESTIMATE):.10f}… → about {round(ESTIMATE)}", 28, OCT_COLOR, bold=True)
        self.text(64, 825, f"Earlier PR #7 draft, RSVP-based: {O_TOTAL} × ({ATTENDED}/{S_TOTAL}) = {ALTERNATE} = {float(ALTERNATE):.10f}… → about {round(ALTERNATE)}", 20, MUTED)
        self.text(64, 861, "84 is a door head count, not verified attendance among the 136 email guests.", 18)
        self.text(64, 889, "84/136 is an aggregate ratio—not an email-guest conversion rate. October reuses it as an assumption.", 18, MUTED)
        as_of = datetime.fromisoformat(OCT["as_of"].replace("Z", "+00:00"))
        local = as_of.astimezone(ZoneInfo("America/Los_Angeles"))
        stamp = local.strftime("%b %-d, %Y · %-I:%M:%S %p %Z")
        self.text(64, 937, f"October snapshot: {stamp} ({as_of.strftime('%H:%M:%S UTC')}). Not a live count.", 17, MUTED)
        self.text(64, 964, f"RSVPs: September {SEP['named_guests']} named + {SEP['unnamed_plus_ones']} plus-ones; October {OCT['named_guests']} + {OCT['unnamed_plus_ones']}.", 17, MUTED)
        self.text(64, 991, "Later build notes report 133 named guests; this comparison deliberately retains the saved 132-row snapshot.", 17, MUTED)

    def save(self, name, *, footer=True):
        if footer:
            self.footer()
        image = self.image.resize((self.width, self.height), Image.Resampling.LANCZOS)
        path = HERE / name
        image.save(path)
        print(f"Rendered {path.relative_to(ROOT)} ({self.width} × {self.height})")


def option_a():
    width, height = 720, 540
    measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    xs = (169, 374, 579)

    def y(value):
        return 400 - math.log(float(value) / 40) / math.log(260 / 40) * 310

    axis_y = 430

    series = (
        ("Sept.", (S_TOTAL, S_EMAIL, ATTENDED), SEPT_COLOR),
        ("Oct.", (O_TOTAL, O_EMAIL, ESTIMATE), OCT_COLOR),
    )
    segments = [
        ((xs[i], y(counts[i])), (xs[i+1], y(counts[i+1])))
        for _, counts, _ in series for i in range(2)
    ]
    boxes = []
    # Each placed label: (row or None for static, stage it appears at, x, y, text, size, color, anchor).
    labels = []

    def label_box(x, yy, text, size, anchor):
        bounds = measure.textbbox((x*SCALE, yy*SCALE), text, font=FONTS[size], anchor=anchor)
        return tuple(v/SCALE for v in bounds)

    # September's labels sit above its line; October's sit below its line.
    value_offset = {"Sept.": -26, "Oct.": 30}
    oct_value_bottom = label_box(xs[1], y(O_EMAIL) + value_offset["Oct."], str(O_EMAIL), 22, "mm")[3]
    # Dashed guides rise from the shared axis row to each column's lowest dot, or stop short of
    # October's middle count label with a small gap.
    guides = [
        ((x, oct_value_bottom + 8 if i == 1 else max(y(counts[i]) for _, counts, _ in series) + 6),
         (x, axis_y - 18))
        for i, x in enumerate(xs)
    ]

    def clear(box):
        expanded = (box[0]-6, box[1]-6, box[2]+6, box[3]+6)
        return (
            not any(segment_hits_box(start, end, expanded) for start, end in segments + guides)
            and not any(box[0]-3 < b[2] and box[2]+3 > b[0]
                        and box[1]-3 < b[3] and box[3]+3 > b[1] for b in boxes)
        )

    def label(x, yy, text, size=20, color=TEXT, anchor="mm", *, row=None, stage=0):
        box = label_box(x, yy, text, size, anchor)
        if not clear(box):
            raise ValueError(f"Label has insufficient line or text clearance: {text}")
        labels.append((row, stage, x, yy, text, size, color, anchor))
        boxes.append(box)

    label(40, 40, f"October is on pace for ≈{round(ESTIMATE)} attendees", 28, anchor="lm")
    label(680, 40, "as of Oct. 27, 2026", 16, MUTED, "rm")
    for (start, end), text in zip(guides, ("RSVPs", "Email", "Attended")):
        label(start[0], axis_y, text, 17, MUTED)
    for row, (name, counts, color) in enumerate(series):
        ys = [y(v) for v in counts]
        for i, (x, yy, value) in enumerate(zip(xs, ys, counts)):
            estimated = name == "Oct." and i == 2
            if i == 0:
                # Left labels stay visible throughout, as in the existing slopegraph.
                label(x-12, yy, f"{name} {value}", 20, color, "rm")
            elif i == 1:
                label(x, yy + value_offset[name], str(value), 22, color, row=row, stage=1)
            else:
                # Drop end labels slightly so they continue the downward slope.
                label(x+12, yy+8, f"≈{round(value)}" if estimated else str(value), 22, color, "lm",
                      row=row, stage=2)
                if estimated:
                    label(x+12, yy+32, "assumed", 17, color, "lm", row=row, stage=2)
    for row, (name, counts, color) in enumerate(series):
        ratios = (S_SHARE if row == 0 else O_SHARE, RATIO)
        for i, ratio in enumerate(ratios):
            start, end = segments[row*2+i]
            dx, dy = end[0]-start[0], end[1]-start[1]
            length = math.hypot(dx, dy)
            text = f"{round(float(ratio) * 100)}%"
            side = 1 if row == 0 else -1
            for offset in range(24, 121, 4):
                x = (start[0]+end[0])/2 + dy/length*offset*side
                yy = (start[1]+end[1])/2 - dx/length*offset*side
                if clear(label_box(x, yy, text, 20, "mm")):
                    # A step's ratio appears once the line reaches that step's end.
                    label(x, yy, text, 20, color, row=row, stage=i+1)
                    break
            else:
                raise ValueError(f"No clear position for {text}")
    label(40, 490, "Same slope = same share kept, so the smaller October list compares fairly.", 16, MUTED, "lm")
    label(40, 514, "We don’t know which of the 84 attendees had email, so 62% is a rough guide.", 16, MUTED, "lm")

    count = len(series)
    travel = 1 - STAGGER * (count - 1)

    def frame(overall):
        """Draw one moment; reuses the existing GIF's stagger, easing and label fade."""
        c = Canvas(width=width, height=height)
        for start, end in guides:
            c.line(start, end, fade(MUTED, 0.5), 1, dashed=True)
        for row, (name, counts, color) in enumerate(series):
            progress = line_progress(overall, row, count)
            points = [(x, y(v)) for x, v in zip(xs, counts)]
            tip_x = xs[0] + (xs[2] - xs[0]) * progress
            for i in range(2):
                (x0, y0), (x1, y1) = points[i], points[i+1]
                if tip_x <= x0:
                    break
                share = min((tip_x - x0) / (x1 - x0), 1)
                c.line((x0, y0), (x0 + (x1-x0)*share, y0 + (y1-y0)*share), color, 2,
                       dashed=name == "Oct." and i == 1)
            c.dot(*points[0], color, radius=3)
            if progress >= 0.5:
                c.dot(*points[1], color, radius=3)
            if 0 < progress:
                i = 0 if progress < 0.5 else 1
                (x0, y0), (x1, y1) = points[i], points[i+1]
                share = (tip_x - x0) / (x1 - x0)
                c.dot(x0 + (x1-x0)*share, y0 + (y1-y0)*share, color,
                      hollow=name == "Oct." and i == 1, radius=3)
        for row, stage, x, yy, text, size, color, anchor in labels:
            amount = 1
            if row is not None:
                # Stage 1 arrives halfway along the eased reveal; stage 2 arrives at the end.
                arrived_at = STAGGER * row + travel * stage / 2
                amount = (overall - arrived_at) / LABEL_FADE
                if amount <= 0:
                    continue
            c.text(x, yy, text, size, fade(color, amount) if amount < 1 else color, anchor=anchor)
        return c.image.resize((width, height), Image.Resampling.LANCZOS)

    # Run past 1.0 so the last labels finish fading in before the final hold.
    end = 1 + LABEL_FADE
    still = HERE / "option-a-log-scale-three-stage-slopegraph.png"
    frame(end).save(still)
    print(f"Rendered {still.relative_to(ROOT)} ({width} × {height})")
    print(f"Option A: {len(boxes)} labels clear all four segments and three guides by at least 6 px; no text overlaps.")

    encoder = shutil.which("gifski")
    if encoder is None:
        raise AnimationError("Cannot render Option A animation: install Gifski (brew install gifski on macOS)")
    gif = HERE / "option-a-log-scale-three-stage-slopegraph.gif"
    with tempfile.TemporaryDirectory(prefix="rsvp-funnel-") as directory:
        paths = []
        for step in range(MOTION_STEPS + 1):
            path = Path(directory) / f"frame-{step:04d}.png"
            frame(end * step / MOTION_STEPS).save(path, compress_level=1)
            paths.append(str(path))
        # Same holds as the existing slopegraph: a short opening pause and a long final hold.
        inputs = paths[:1] * OPENING_HOLD_FRAMES + paths[1:-1] + paths[-1:] * FINAL_HOLD_FRAMES
        result = subprocess.run(
            [encoder, "--quiet", "--no-sort", "--fps", str(FPS), "--quality", "100",
             "--motion-quality", "100", "--lossy-quality", "100", "--width", str(width),
             "--height", str(height), "--repeat", "-1", "--output", str(gif), *inputs],
            capture_output=True, text=True, check=False,
        )
    if result.returncode != 0:
        raise AnimationError(f"Gifski failed: {result.stderr.strip() or result.stdout.strip()}")
    seconds = (OPENING_HOLD_FRAMES + MOTION_STEPS - 1 + FINAL_HOLD_FRAMES) / FPS
    print(f"Rendered {gif.relative_to(ROOT)} ({width} × {height}, {FPS} fps, {seconds:.2f} s, plays once)")


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
