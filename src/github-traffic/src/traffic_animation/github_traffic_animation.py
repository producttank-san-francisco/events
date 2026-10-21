#!/usr/bin/env python3
"""Render a square animated GIF from validated GitHub traffic data."""

from __future__ import annotations

import math
import shutil
import subprocess
import tempfile
from datetime import datetime
from itertools import accumulate
from pathlib import Path
from typing import Any, NamedTuple, Sequence

from PIL import Image, ImageDraw, ImageFont

WIDTH = 720
HEIGHT = 720
RENDER_SCALE = 3
FPS = 25
# 108 steps instead of 72 slows the reveal by one-third at the same frame rate.
MOTION_STEPS = 108
OPENING_HOLD_FRAMES = 9
FINAL_HOLD_FRAMES = 40
BACKGROUND = "#071f28"
TEXT = "#f4f7f8"
MUTED = "#9bb2bd"
GRID = "#173640"
VIEWS = "#ffbd4a"
CLONES = "#29c2e1"
FONT_CANDIDATES = (
    Path("/System/Library/Fonts/SFNS.ttf"),
    Path("/System/Library/Fonts/SFCompact.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
)
BOLD_FONT_CANDIDATES = (
    Path("/System/Library/Fonts/SFNS.ttf"),
    Path("/System/Library/Fonts/SFCompact.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
)


class AnimationError(RuntimeError):
    """A user-actionable GIF encoder failure."""


class Fonts(NamedTuple):
    brand: ImageFont.FreeTypeFont | ImageFont.ImageFont
    title: ImageFont.FreeTypeFont | ImageFont.ImageFont
    subtitle: ImageFont.FreeTypeFont | ImageFont.ImageFont
    axis: ImageFont.FreeTypeFont | ImageFont.ImageFont
    label: ImageFont.FreeTypeFont | ImageFont.ImageFont
    note: ImageFont.FreeTypeFont | ImageFont.ImageFont


def load_font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    size *= RENDER_SCALE
    candidates = BOLD_FONT_CANDIDATES if bold else FONT_CANDIDATES
    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            if path.exists():
                raise
    return ImageFont.load_default(size=size)


def load_fonts() -> Fonts:
    return Fonts(
        brand=load_font(15, bold=True),
        title=load_font(38, bold=True),
        subtitle=load_font(19),
        axis=load_font(16),
        label=load_font(18, bold=True),
        note=load_font(13),
    )


def nice_axis_max(value: int) -> int:
    if value <= 0:
        return 1
    raw_step = value / 4
    magnitude = 10 ** math.floor(math.log10(raw_step))
    normalized = raw_step / magnitude
    if normalized <= 1:
        step = 1
    elif normalized <= 2:
        step = 2
    elif normalized <= 2.5:
        step = 2.5
    elif normalized <= 5:
        step = 5
    else:
        step = 10
    return math.ceil(step * magnitude * 4)


def format_date(timestamp: str, *, include_year: bool = False) -> str:
    value = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    return value.strftime("%b %-d, %Y" if include_year else "%b %-d")


def series_from_snapshot(snapshot: dict[str, Any]) -> tuple[list[str], list[int], list[int]]:
    view_rows = snapshot["views"]["views"]
    clone_rows = {row["timestamp"][:10]: row["count"] for row in snapshot["clones"]["clones"]}
    activity = [row["count"] + clone_rows.get(row["timestamp"][:10], 0) for row in view_rows]
    active_indexes = [index for index, count in enumerate(activity) if count]
    if active_indexes:
        view_rows = view_rows[active_indexes[0] : active_indexes[-1] + 1]
    dates = [row["timestamp"] for row in view_rows]
    views = list(accumulate(row["count"] for row in view_rows))
    clones = list(accumulate(clone_rows.get(row["timestamp"][:10], 0) for row in view_rows))
    return dates, views, clones


def peak_date(snapshot: dict[str, Any]) -> str:
    view_rows = snapshot["views"]["views"]
    clone_rows = {row["timestamp"][:10]: row["count"] for row in snapshot["clones"]["clones"]}
    peak = max(
        view_rows,
        key=lambda row: row["count"] + clone_rows.get(row["timestamp"][:10], 0),
    )
    return format_date(peak["timestamp"])


def line_points(
    values: Sequence[int],
    progress: float,
    *,
    x_start: int,
    x_end: int,
    y_top: int,
    y_bottom: int,
    axis_max: int,
) -> list[tuple[float, float]]:
    if len(values) == 1:
        x_step = 0.0
    else:
        x_step = (x_end - x_start) / (len(values) - 1)
    completed = min(int(progress), len(values) - 1)
    points = [
        (x_start + index * x_step, y_bottom - (values[index] / axis_max) * (y_bottom - y_top))
        for index in range(completed + 1)
    ]
    fraction = progress - completed
    if fraction > 0 and completed + 1 < len(values):
        next_x = x_start + (completed + fraction) * x_step
        interpolated = values[completed] + fraction * (values[completed + 1] - values[completed])
        next_y = y_bottom - (interpolated / axis_max) * (y_bottom - y_top)
        points.append((next_x, next_y))
    return points


def draw_series(
    draw: ImageDraw.ImageDraw,
    values: Sequence[int],
    progress: float,
    *,
    color: str,
    label: str,
    label_offset: int,
    axis_max: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> None:
    points = line_points(
        values,
        progress,
        x_start=88 * RENDER_SCALE,
        x_end=536 * RENDER_SCALE,
        y_top=268 * RENDER_SCALE,
        y_bottom=558 * RENDER_SCALE,
        axis_max=axis_max,
    )
    if len(points) > 1:
        draw.line(points, fill=color, width=4 * RENDER_SCALE, joint="curve")
    end_x, end_y = points[-1]
    radius = 4 * RENDER_SCALE
    draw.ellipse((end_x - radius, end_y - radius, end_x + radius, end_y + radius), fill=color)
    current_index = min(int(progress), len(values) - 1)
    fraction = progress - current_index
    current_value = values[current_index]
    if fraction > 0 and current_index + 1 < len(values):
        current_value = round(current_value + fraction * (values[current_index + 1] - current_value))
    label_y = end_y + label_offset * RENDER_SCALE
    draw.line(
        (end_x + 6 * RENDER_SCALE, end_y, end_x + 17 * RENDER_SCALE, label_y + 8 * RENDER_SCALE),
        fill=color,
        width=RENDER_SCALE,
    )
    draw.text((end_x + 21 * RENDER_SCALE, label_y), f"{label} {current_value:,}", fill=color, font=font)


def render_frame(
    snapshot: dict[str, Any],
    dates: Sequence[str],
    views: Sequence[int],
    clones: Sequence[int],
    progress: float,
    axis_max: int,
    headline: str,
    fonts: Fonts,
) -> Image.Image:
    scale = RENDER_SCALE
    image = Image.new("RGB", (WIDTH * scale, HEIGHT * scale), BACKGROUND)
    draw = ImageDraw.Draw(image)

    draw.ellipse((63 * scale, 25 * scale, 77 * scale, 39 * scale), outline=CLONES, width=2 * scale)
    draw.line((67 * scale, 28 * scale, 73 * scale, 36 * scale), fill=VIEWS, width=2 * scale)
    draw.text((86 * scale, 23 * scale), "GitHub traffic", fill=TEXT, font=fonts.brand)

    date_index = min(round(progress), len(dates) - 1)
    current_date = format_date(dates[date_index], include_year=True)
    date_width = draw.textbbox((0, 0), current_date, font=fonts.axis)[2]
    draw.text((658 * scale - date_width, 25 * scale), current_date, fill=MUTED, font=fonts.axis)

    draw.text((62 * scale, 68 * scale), headline, fill=TEXT, font=fonts.title)
    draw.text((62 * scale, 119 * scale), "Cumulative page views and Git clones", fill=MUTED, font=fonts.subtitle)

    for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
        y = (558 - fraction * (558 - 268)) * scale
        value = round(axis_max * fraction)
        draw.line((87 * scale, y, 537 * scale, y), fill=GRID, width=scale)
        tick = f"{value:,}"
        tick_width = draw.textbbox((0, 0), tick, font=fonts.axis)[2]
        draw.text((74 * scale - tick_width, y - 10 * scale), tick, fill=MUTED, font=fonts.axis)

    draw_series(
        draw,
        views,
        progress,
        color=VIEWS,
        label="Views",
        label_offset=-22,
        axis_max=axis_max,
        font=fonts.label,
    )
    draw_series(
        draw,
        clones,
        progress,
        color=CLONES,
        label="Clones",
        label_offset=10,
        axis_max=axis_max,
        font=fonts.label,
    )

    first_date = format_date(dates[0])
    last_date = format_date(dates[-1])
    draw.text((87 * scale, 578 * scale), first_date, fill=MUTED, font=fonts.axis)
    last_width = draw.textbbox((0, 0), last_date, font=fonts.axis)[2]
    draw.text((537 * scale - last_width, 578 * scale), last_date, fill=MUTED, font=fonts.axis)
    draw.text((62 * scale, 625 * scale), f"{snapshot['repository']} · UTC", fill=MUTED, font=fonts.note)
    draw.text((62 * scale, 647 * scale), "Clones can include automated systems.", fill=MUTED, font=fonts.note)
    return image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def render_traffic_gif(snapshot: dict[str, Any]) -> bytes:
    encoder = shutil.which("gifski")
    if encoder is None:
        raise AnimationError("Cannot render traffic animation: install Gifski (brew install gifski on macOS)")
    dates, views, clones = series_from_snapshot(snapshot)
    if not dates:
        raise ValueError("Cannot render traffic animation without daily data")
    axis_max = nice_axis_max(max(views[-1], clones[-1]))
    headline = f"Traffic peaked on {peak_date(snapshot)}."
    fonts = load_fonts()
    final_progress = len(dates) - 1
    # Smoothstep eases the reveal without changing the measured daily points.
    if final_progress:
        progress_values = []
        for step in range(MOTION_STEPS + 1):
            fraction = step / MOTION_STEPS
            progress_values.append(final_progress * (3 * fraction ** 2 - 2 * fraction ** 3))
    else:
        progress_values = [0.0]

    with tempfile.TemporaryDirectory(prefix="github-traffic-") as temporary_directory:
        directory = Path(temporary_directory)
        frame_paths = []
        for index, progress in enumerate(progress_values):
            frame_path = directory / f"frame-{index:04d}.png"
            frame = render_frame(snapshot, dates, views, clones, progress, axis_max, headline, fonts)
            frame.save(frame_path, compress_level=1)
            frame.close()
            frame_paths.append(str(frame_path))
        # Repeated inputs give Gifski exact holds without re-quantizing its output.
        inputs = (
            frame_paths[:1] * OPENING_HOLD_FRAMES
            + frame_paths[1:-1]
            + frame_paths[-1:] * FINAL_HOLD_FRAMES
        )
        output_path = directory / "traffic.gif"
        command = [
            encoder, "--quiet", "--no-sort",
            "--fps", str(FPS),
            "--quality", "100",
            "--motion-quality", "100",
            "--lossy-quality", "100",
            "--width", str(WIDTH),
            "--height", str(HEIGHT),
            "--repeat", "0",
            "--output", str(output_path),
            *inputs,
        ]
        try:
            result = subprocess.run(command, capture_output=True, text=True, check=False)
        except OSError as error:
            raise AnimationError(f"Cannot run Gifski: {error}") from error
        if result.returncode != 0:
            detail = result.stderr.strip() or result.stdout.strip() or "no error detail returned"
            raise AnimationError(f"Gifski failed: {detail}")
        return output_path.read_bytes()
