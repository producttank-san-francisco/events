#!/usr/bin/env python3
"""Render an animated September-vs-October RSVP slopegraph and its report page."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, NamedTuple, Sequence

from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parents[3]
# Reuse the September traffic animation's palette, fonts and timing so both GIFs match.
sys.path.insert(0, str(REPO_ROOT / "src" / "github-traffic" / "src"))
from traffic_animation.github_traffic_animation import (  # noqa: E402
    BACKGROUND,
    CLONES,
    FPS,
    HEIGHT,
    MUTED,
    RENDER_SCALE,
    TEXT,
    VIEWS,
    WIDTH,
    AnimationError,
    Fonts,
    load_fonts,
)

DEFAULT_DIR = REPO_ROOT / "docs" / "reports" / "rsvp-slopegraph"
MOTION_STEPS = 90
OPENING_HOLD_FRAMES = 9
FINAL_HOLD_FRAMES = 75
# Each line starts this much later than the one above it (fraction of the reveal).
STAGGER = 0.12
LABEL_FADE = 0.08
MARGIN_LEFT = 62
MARGIN_RIGHT = 658
PLOT_TOP = 222
PLOT_BOTTOM = 560
LABEL_GAP = 22
DASH = 9
DASH_SPACE = 7


class Stat(NamedTuple):
    name: str
    september: int
    october: int
    estimate: bool


class Placed(NamedTuple):
    stat: Stat
    left_y: float
    right_y: float
    left_label_y: float
    right_label_y: float


class Layout(NamedTuple):
    x_left: float
    x_right: float
    placed: list[Placed]


def rsvps(event: dict[str, Any]) -> int:
    return event["named_guests"] + event["unnamed_plus_ones"]


def turnout_rate(september: dict[str, Any]) -> float:
    """September turnout as an unrounded ratio."""
    return september["attended"] / rsvps(september)


def load_stats(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text())
    required = {
        "september": ("label", "venue", "named_guests", "guests_with_email", "unnamed_plus_ones", "attended"),
        "october": ("label", "venue", "as_of", "named_guests", "guests_with_email", "unnamed_plus_ones"),
    }
    for event, keys in required.items():
        missing = [key for key in keys if key not in data.get(event, {})]
        if missing:
            raise ValueError(f"{path}: {event} is missing {', '.join(missing)}")
        for key in ("named_guests", "guests_with_email", "unnamed_plus_ones", "attended"):
            if key in keys:
                value = data[event][key]
                if type(value) is not int or value < 0:
                    raise ValueError(f"{path}: {event}.{key} must be a non-negative whole number")
    return data


def build_stats(data: dict[str, Any]) -> list[Stat]:
    september, october = data["september"], data["october"]
    estimate = round(rsvps(october) * turnout_rate(september))
    return [
        Stat("RSVPs", rsvps(september), rsvps(october), False),
        Stat("Named guests", september["named_guests"], october["named_guests"], False),
        Stat("Guests with email", september["guests_with_email"], october["guests_with_email"], False),
        Stat("Attended", september["attended"], estimate, True),
    ]


def spread_labels(wanted: Sequence[float], gap: float, top: float, bottom: float) -> list[float]:
    """Move label centers at least `gap` apart, keeping each crowded group centered on its lines.

    Only crowded groups move; a group that would cross `top` or `bottom` slides back inside.
    """

    def clamp(members: list[int], start: float) -> tuple[list[int], float]:
        return members, min(max(start, top), bottom - (len(members) - 1) * gap)

    clusters: list[tuple[list[int], float]] = []  # (members in y order, first member's y)
    for index in sorted(range(len(wanted)), key=lambda i: wanted[i]):
        clusters.append(clamp([index], wanted[index]))
        while len(clusters) > 1:
            (above, above_start), (below, below_start) = clusters[-2], clusters[-1]
            if below_start - (above_start + (len(above) - 1) * gap) >= gap:
                break
            members = above + below
            mean = sum(wanted[member] for member in members) / len(members)
            clusters[-2:] = [clamp(members, mean - (len(members) - 1) * gap / 2)]
    placed = [0.0] * len(wanted)
    for members, start in clusters:
        for offset, member in enumerate(members):
            placed[member] = start + offset * gap
    return placed


def smoothstep(fraction: float) -> float:
    fraction = min(max(fraction, 0.0), 1.0)
    return 3 * fraction**2 - 2 * fraction**3


def line_progress(overall: float, index: int, count: int) -> float:
    return smoothstep((overall - STAGGER * index) / (1 - STAGGER * (count - 1)))


def fade(color: str, amount: float) -> tuple[int, ...]:
    start = Image.new("RGB", (1, 1), BACKGROUND).getpixel((0, 0))
    end = Image.new("RGB", (1, 1), color).getpixel((0, 0))
    amount = min(max(amount, 0.0), 1.0)
    return tuple(round(a + (b - a) * amount) for a, b in zip(start, end))


def draw_dashed(draw: ImageDraw.ImageDraw, start: tuple[float, float], end: tuple[float, float], color: str, width: int) -> None:
    length = math.dist(start, end)
    if length == 0:
        return
    dx, dy = (end[0] - start[0]) / length, (end[1] - start[1]) / length
    position = 0.0
    while position < length:
        stop = min(position + DASH * RENDER_SCALE, length)
        draw.line(
            (start[0] + dx * position, start[1] + dy * position, start[0] + dx * stop, start[1] + dy * stop),
            fill=color,
            width=width,
        )
        position = stop + DASH_SPACE * RENDER_SCALE


def format_as_of(timestamp: str) -> str:
    return datetime.fromisoformat(timestamp.replace("Z", "+00:00")).strftime("%b %-d, %Y, %H:%M UTC")


def right_value(stat: Stat) -> str:
    return f"~{stat.october:,}" if stat.estimate else f"{stat.october:,}"


def right_name(stat: Stat) -> str:
    return f"{stat.name} (estimate)" if stat.estimate else stat.name


def headline(stats: Sequence[Stat]) -> str:
    total = stats[0]
    change = round((total.october - total.september) / total.september * 100)
    return f"October RSVPs are {'down' if change < 0 else 'up'} {abs(change)}% so far."


def plan_layout(stats: Sequence[Stat], fonts: Fonts, draw: ImageDraw.ImageDraw) -> Layout:
    scale = RENDER_SCALE
    left_width = max(
        draw.textlength(f"{stat.name}  ", font=fonts.axis) + draw.textlength(f"{stat.september:,}", font=fonts.label)
        for stat in stats
    )
    right_width = max(
        draw.textlength(right_value(stat), font=fonts.label) + draw.textlength(f"  {right_name(stat)}", font=fonts.axis)
        for stat in stats
    )
    # 24 px leaves room for a nudged label's leader line.
    x_left = MARGIN_LEFT * scale + left_width + 24 * scale
    x_right = MARGIN_RIGHT * scale - right_width - 24 * scale
    if x_right - x_left < 140 * scale:
        raise ValueError("Labels are too wide for the slopegraph")
    axis_max = max(max(stat.september, stat.october) for stat in stats)

    def y_for(value: int) -> float:
        return (PLOT_BOTTOM - value / axis_max * (PLOT_BOTTOM - PLOT_TOP)) * scale

    left_y = [y_for(stat.september) for stat in stats]
    right_y = [y_for(stat.october) for stat in stats]
    # Labels may sit a little outside the line area: below the column headers, above the notes.
    bounds = ((PLOT_TOP - LABEL_GAP) * scale, (PLOT_BOTTOM + LABEL_GAP) * scale)
    left_labels = spread_labels(left_y, LABEL_GAP * scale, *bounds)
    right_labels = spread_labels(right_y, LABEL_GAP * scale, *bounds)
    placed = [Placed(stat, left_y[i], right_y[i], left_labels[i], right_labels[i]) for i, stat in enumerate(stats)]
    return Layout(x_left, x_right, placed)


def draw_label(
    draw: ImageDraw.ImageDraw,
    *,
    anchor_x: float,
    line_y: float,
    label_y: float,
    left: bool,
    value: str,
    name: str,
    value_color: Any,
    name_color: Any,
    fonts: Fonts,
) -> None:
    scale = RENDER_SCALE
    value_width = draw.textlength(value, font=fonts.label)
    space = draw.textlength("  ", font=fonts.axis)
    nudged = abs(label_y - line_y) > LABEL_GAP * scale / 3
    sign = -1 if left else 1
    edge = anchor_x + sign * (20 if nudged else 10) * scale
    if nudged:
        draw.line((anchor_x + sign * 7 * scale, line_y, edge - sign * 3 * scale, label_y), fill=name_color, width=scale)
    anchor = "rm" if left else "lm"
    draw.text((edge, label_y), value, fill=value_color, font=fonts.label, anchor=anchor)
    draw.text((edge + sign * (value_width + space), label_y), name, fill=name_color, font=fonts.axis, anchor=anchor)


def render_frame(data: dict[str, Any], stats: Sequence[Stat], layout: Layout, overall: float, fonts: Fonts) -> Image.Image:
    scale = RENDER_SCALE
    september, october = data["september"], data["october"]
    image = Image.new("RGB", (WIDTH * scale, HEIGHT * scale), BACKGROUND)
    draw = ImageDraw.Draw(image)

    draw.ellipse((63 * scale, 25 * scale, 77 * scale, 39 * scale), outline=CLONES, width=2 * scale)
    draw.line((67 * scale, 28 * scale, 73 * scale, 36 * scale), fill=VIEWS, width=2 * scale)
    draw.text((86 * scale, 23 * scale), "ProductTank SF events", fill=TEXT, font=fonts.brand)
    draw.text((658 * scale, 25 * scale), "RSVPs and turnout", fill=MUTED, font=fonts.axis, anchor="ra")
    draw.text((62 * scale, 68 * scale), headline(stats), fill=TEXT, font=fonts.title)
    draw.text(
        (62 * scale, 119 * scale),
        f"{september['label']} at {september['venue']} vs. {october['label']} at {october['venue']}",
        fill=MUTED,
        font=fonts.subtitle,
    )
    draw.text((layout.x_left, 184 * scale), september["label"], fill=TEXT, font=fonts.label, anchor="mm")
    draw.text((layout.x_right, 184 * scale), october["label"], fill=TEXT, font=fonts.label, anchor="mm")

    count = len(layout.placed)
    for index, item in enumerate(layout.placed):
        stat = item.stat
        draw_label(
            draw, anchor_x=layout.x_left, line_y=item.left_y, label_y=item.left_label_y, left=True,
            value=f"{stat.september:,}", name=stat.name, value_color=TEXT, name_color=MUTED, fonts=fonts,
        )
        progress = line_progress(overall, index, count)
        start = (layout.x_left, item.left_y)
        tip = (
            layout.x_left + (layout.x_right - layout.x_left) * progress,
            item.left_y + (item.right_y - item.left_y) * progress,
        )
        color = VIEWS if stat.estimate else CLONES
        if stat.estimate:
            draw_dashed(draw, start, tip, color, 3 * scale)
        else:
            draw.line((*start, *tip), fill=color, width=3 * scale)
        radius = 4 * scale
        for x, y in (start, tip):
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), fill=color)
        # The end label fades in over LABEL_FADE once its line has arrived.
        arrived_at = STAGGER * index + 1 - STAGGER * (count - 1)
        reveal = (overall - arrived_at) / LABEL_FADE
        if progress >= 1:
            draw_label(
                draw, anchor_x=layout.x_right, line_y=item.right_y, label_y=item.right_label_y, left=False,
                value=right_value(stat), name=right_name(stat),
                value_color=fade(TEXT, reveal), name_color=fade(MUTED, reveal), fonts=fonts,
            )
            if stat.name in ("RSVPs", "Guests with email"):
                change = round((stat.october - stat.september) / stat.september * 100)
                draw.text(
                    ((layout.x_left + layout.x_right) / 2, (item.left_y + item.right_y) / 2 - 16 * scale),
                    f"{change:+d}%".replace("-", "−"),
                    fill=fade(TEXT, reveal),
                    font=fonts.label,
                    anchor="mm",
                )

    rate = round(turnout_rate(september) * 100)
    draw.text(
        (62 * scale, 625 * scale),
        "RSVPs = named guests + unnamed Meetup plus-ones. Aggregate counts only.",
        fill=MUTED,
        font=fonts.note,
    )
    draw.text(
        (62 * scale, 647 * scale),
        f"October as of {format_as_of(october['as_of'])}; attended is an estimate at September’s {rate}% turnout.",
        fill=MUTED,
        font=fonts.note,
    )
    return image.resize((WIDTH, HEIGHT), Image.Resampling.LANCZOS)


def render_slopegraph_gif(data: dict[str, Any]) -> bytes:
    encoder = shutil.which("gifski")
    if encoder is None:
        raise AnimationError("Cannot render slopegraph animation: install Gifski (brew install gifski on macOS)")
    stats = build_stats(data)
    fonts = load_fonts()
    layout = plan_layout(stats, fonts, ImageDraw.Draw(Image.new("RGB", (1, 1))))
    # Run past 1.0 so the last end label finishes fading in before the final hold.
    end = 1 + LABEL_FADE
    with tempfile.TemporaryDirectory(prefix="rsvp-slopegraph-") as temporary_directory:
        directory = Path(temporary_directory)
        frame_paths = []
        for step in range(MOTION_STEPS + 1):
            frame_path = directory / f"frame-{step:04d}.png"
            frame = render_frame(data, stats, layout, end * step / MOTION_STEPS, fonts)
            frame.save(frame_path, compress_level=1)
            frame.close()
            frame_paths.append(str(frame_path))
        # Repeated inputs give Gifski exact holds, as in the traffic animation.
        inputs = frame_paths[:1] * OPENING_HOLD_FRAMES + frame_paths[1:-1] + frame_paths[-1:] * FINAL_HOLD_FRAMES
        output_path = directory / "slopegraph.gif"
        command = [
            encoder, "--quiet", "--no-sort",
            "--fps", str(FPS),
            "--quality", "100",
            "--motion-quality", "100",
            "--lossy-quality", "100",
            "--width", str(WIDTH),
            "--height", str(HEIGHT),
            "--repeat", "-1",
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


def render_report(data: dict[str, Any], gif_name: str) -> str:
    stats = build_stats(data)
    september, october = data["september"], data["october"]
    rate = round(turnout_rate(september) * 100)
    rows = "\n".join(
        f"| {stat.name} | {stat.september:,} | {right_value(stat)}{' (estimate)' if stat.estimate else ''} |"
        for stat in stats
    )
    return f"""# ProductTank SF: September vs. October RSVPs

> **{headline(stats)}** {september['label']} at {september['venue']} drew {stats[0].september:,} RSVPs; {october['label']} at {october['venue']} has {stats[0].october:,} so far.

![Animated slopegraph comparing September and October event stats]({gif_name})

| Stat | {september['label']} | {october['label']} |
| --- | ---: | ---: |
{rows}

- RSVPs are named guests plus unnamed Meetup plus-ones.
- September attended is the door head count.
- October as of {format_as_of(october['as_of'])}; attended is an estimate at September’s {rate}% turnout.
- Aggregate counts only. No guest names or emails are stored in this repository.

To refresh, edit [`stats.json`](stats.json), then run `./src/rsvp-slopegraph/src/rsvp_slopegraph.py` from the repository root.
"""


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DIR / "stats.json", help="aggregate stats JSON")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DIR, help="where to write slopegraph.gif and report.md")
    args = parser.parse_args(argv)
    try:
        data = load_stats(args.data)
        gif = render_slopegraph_gif(data)
    except (ValueError, AnimationError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    args.output_dir.mkdir(parents=True, exist_ok=True)
    gif_path = args.output_dir / "slopegraph.gif"
    report_path = args.output_dir / "report.md"
    gif_path.write_bytes(gif)
    report_path.write_text(render_report(data, gif_path.name))
    print(f"Wrote {report_path}\nWrote {gif_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
