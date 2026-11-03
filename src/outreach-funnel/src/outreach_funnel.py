#!/usr/bin/env python3
"""Render an event outreach funnel as a Tufte-style GIF, PNG and web page."""

from __future__ import annotations

import argparse
import base64
import csv
import html
import io
import json
import math
import re
import sys
import tempfile
from datetime import datetime
from fractions import Fraction
from itertools import combinations
from pathlib import Path
from typing import Any, NamedTuple, Sequence
from zoneinfo import ZoneInfo

from PIL import Image, ImageColor, ImageDraw, ImageFont

MODULE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
# Reuse the traffic animation's supersampling and Gifski encoder, and the slopegraph's reveal timing.
sys.path.insert(0, str(REPO_ROOT / "src" / "github-traffic" / "src"))
sys.path.insert(0, str(REPO_ROOT / "src" / "rsvp-slopegraph" / "src"))
from traffic_animation.github_traffic_animation import RENDER_SCALE, AnimationError, encode_gif, find_gifski  # noqa: E402
from rsvp_slopegraph import (  # noqa: E402
    FINAL_HOLD_FRAMES,
    LABEL_FADE,
    MOTION_STEPS,
    OPENING_HOLD_FRAMES,
    STAGGER,
    line_progress,
)

DEFAULT_DIR = REPO_ROOT / "docs" / "reports" / "outreach-funnel"
ASSETS = MODULE_ROOT / "assets"
TUFTE_CSS = ASSETS / "tufte.css"
ROMAN_FONT = ASSETS / "et-book" / "et-book-roman-line-figures.ttf"
ITALIC_FONT = ASSETS / "et-book" / "et-book-display-italic-old-style-figures.ttf"
BOLD_FONT = ASSETS / "et-book" / "et-book-bold-line-figures.ttf"
TIME_ZONE = ZoneInfo("America/Los_Angeles")
AP_MONTHS = ("Jan.", "Feb.", "March", "April", "May", "June", "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec.")
GIF_NAME = "outreach-funnel.gif"
PNG_NAME = "outreach-funnel.png"
PAGE_NAME = "index.html"

EMAIL_SENT = "Email Sent"
INVITE_DECLINED = "Invite Declined"
LUMA_RSVP = "Luma RSVP"
LUMA_ACCEPT = "Luma Accept"
REQUIRED_COLUMNS = (EMAIL_SENT, INVITE_DECLINED, LUMA_RSVP, LUMA_ACCEPT)

# tufte-css palette: warm off-white paper, near-black ink, warm grays.
WIDTH = 720
MARGIN = 48
BACKGROUND = "#fffff8"
INK = "#111111"
MUTED = "#6f6d66"
TRACK = "#ebe9dd"
DECLINED_BAR = "#a9a69b"
# Vertical rhythm in final pixels: baseline-to-baseline or edge-to-edge gaps.
SUBTITLE_PITCH = 30
ROWS_GAP = 40
BAR_HEIGHT = 17
ROW_PITCH = 44
NOTES_GAP = 46
NOTE_PITCH = 22
NAME_GAP = 12
VALUE_GAP = 16
SHARE_GAP = 8
MIN_BAR_AREA = 200

PAGE_CSS = """
section > table { width: auto; border-collapse: collapse; font-size: 1.4rem; line-height: 2rem; }
th, td { padding: 0 2rem 0 0; text-align: left; font-weight: normal; }
thead th { border-bottom: 1px solid #111; }
th.number, td.number { text-align: right; }
"""
LICENSE_BANNER = (
    "/* tufte-css: Copyright (c) 2014 Dave Liepmann, MIT License. "
    "ET Book: Copyright (c) 2015 Dmitry Krasny, Bonnie Scranton, Edward Tufte, MIT License. */"
)


class SheetError(ValueError):
    """The sheet export cannot be counted as it stands; the message says what to fix."""


class Funnel(NamedTuple):
    listed: int
    invited: int
    bounced: int
    not_invited: int
    declined: int
    rsvped: int
    accepted: int

    @property
    def no_reply(self) -> int:
        return self.invited - self.declined - self.rsvped

    @property
    def waiting(self) -> int:
        return self.rsvped - self.accepted


class Stage(NamedTuple):
    name: str
    count: int
    parent: int | None  # index of the stage this one is counted from
    share: str
    color: str


class Fonts(NamedTuple):
    headline: ImageFont.FreeTypeFont
    subtitle: ImageFont.FreeTypeFont
    label: ImageFont.FreeTypeFont
    share: ImageFont.FreeTypeFont
    note: ImageFont.FreeTypeFont


class Text(NamedTuple):
    xy: tuple[float, float]
    text: str
    font: ImageFont.FreeTypeFont
    anchor: str
    color: str
    row: int | None  # None: shown in every frame; otherwise fades in when that row's bar arrives


class Bar(NamedTuple):
    top: float
    count: int
    parent: int | None
    color: str


class Layout(NamedTuple):
    height: int
    bar_left: float
    unit: float  # render pixels per person, one scale for every bar
    bars: list[Bar]
    texts: list[Text]


def read_sheet(path: Path) -> list[list[str]]:
    """Read a CSV download, or the JSON that `gog sheets get <id> <range> --json` prints."""
    if path.suffix.lower() != ".json":
        with path.open(newline="", encoding="utf-8-sig") as file:
            return list(csv.reader(file))
    data = json.loads(path.read_text(encoding="utf-8"))
    values = data.get("values") if isinstance(data, dict) else None
    if not isinstance(values, list) or not all(isinstance(row, list) for row in values):
        raise SheetError(f'{path} is not a gog sheets export: expected {{"values": [[...], ...]}}')
    return [["" if cell is None else str(cell) for cell in row] for row in values]


def checkbox(value: str, row_number: int, column: str, problems: list[str]) -> bool:
    text = value.strip().upper()
    if text not in ("TRUE", "FALSE", ""):
        problems.append(f"row {row_number}, {column}: expected a checkbox (TRUE, FALSE or blank)")
    return text == "TRUE"


def count_funnel(rows: Sequence[Sequence[str]]) -> Funnel:
    if not rows:
        raise SheetError("The sheet export is empty")
    header = [name.strip() for name in rows[0]]
    missing = [column for column in REQUIRED_COLUMNS if column not in header]
    if missing:
        raise SheetError(f"The sheet is missing column{'s' if len(missing) > 1 else ''}: {', '.join(missing)}")
    columns = {column: header.index(column) for column in REQUIRED_COLUMNS}
    problems: list[str] = []
    listed = invited = bounced = declined = rsvped = accepted = 0
    for row_number, row in enumerate(rows[1:], start=2):
        cells = [*row, *[""] * (len(header) - len(row))]
        if not any(cell.strip() for cell in cells):
            continue
        listed += 1
        sent = cells[columns[EMAIL_SENT]].strip()
        is_bounced = sent.lower() == "bounced"
        is_invited = bool(sent) and not is_bounced
        said_no = checkbox(cells[columns[INVITE_DECLINED]], row_number, INVITE_DECLINED, problems)
        rsvp = checkbox(cells[columns[LUMA_RSVP]], row_number, LUMA_RSVP, problems)
        accept = checkbox(cells[columns[LUMA_ACCEPT]], row_number, LUMA_ACCEPT, problems)
        if accept and not rsvp:
            problems.append(f"row {row_number}, {LUMA_ACCEPT}: checked without {LUMA_RSVP}")
        if not is_invited:
            for column, checked in ((INVITE_DECLINED, said_no), (LUMA_RSVP, rsvp)):
                if checked:
                    reason = "Bounced" if is_bounced else "blank"
                    problems.append(f"row {row_number}, {column}: checked, but {EMAIL_SENT} is {reason}")
        if said_no and rsvp:
            problems.append(f"row {row_number}, {INVITE_DECLINED} and {LUMA_RSVP}: both are checked")
        invited += is_invited
        bounced += is_bounced
        declined += is_invited and said_no
        rsvped += is_invited and rsvp
        accepted += is_invited and rsvp and accept
    if problems:
        heading = "The sheet has 1 problem" if len(problems) == 1 else f"The sheet has {len(problems)} problems"
        raise SheetError(f"{heading}; fix and export again:\n" + "\n".join(f"  {problem}" for problem in problems))
    if invited == 0:
        raise SheetError(f"Nobody is invited yet ({EMAIL_SENT} is blank or Bounced on every row): nothing to chart")
    return Funnel(listed, invited, bounced, listed - invited - bounced, declined, rsvped, accepted)


def plural(count: int, singular: str, plural_form: str | None = None) -> str:
    return f"{count:,} {singular if count == 1 else plural_form or singular + 's'}"


def percent(part: int, whole: int) -> int:
    """Whole percent of the exact fraction, with halves rounded up."""
    return math.floor(Fraction(100 * part, whole) + Fraction(1, 2))


def stages(funnel: Funnel) -> list[Stage]:
    accepted_share = f"{percent(funnel.accepted, funnel.rsvped)}% of RSVPs" if funnel.rsvped else ""
    return [
        Stage("Invited", funnel.invited, None, "", INK),
        Stage("Declined", funnel.declined, 0, f"{percent(funnel.declined, funnel.invited)}% of invited", DECLINED_BAR),
        Stage("RSVP’d", funnel.rsvped, 0, f"{percent(funnel.rsvped, funnel.invited)}% of invited", INK),
        Stage("Accepted", funnel.accepted, 2, accepted_share, INK),
    ]


def headline(funnel: Funnel) -> str:
    invitees = plural(funnel.invited, "invitee")
    if not funnel.rsvped:
        return f"None of {invitees} has RSVP’d yet."
    verb = "is" if funnel.accepted == 1 else "are"
    return f"{funnel.rsvped:,} of {invitees} RSVP’d; {funnel.accepted:,} {verb} accepted."


def notes(funnel: Funnel) -> list[str]:
    replies = []
    if funnel.no_reply:
        replies.append(f"{plural(funnel.no_reply, 'invitee')} {'has' if funnel.no_reply == 1 else 'have'} not replied.")
    if funnel.waiting:
        replies.append(f"{plural(funnel.waiting, 'RSVP')} {'awaits' if funnel.waiting == 1 else 'await'} host approval.")
    skipped = []
    if funnel.bounced:
        skipped.append(plural(funnel.bounced, "bounced email"))
    if funnel.not_invited:
        skipped.append(f"{plural(funnel.not_invited, 'person', 'people')} not yet contacted")
    rule = "Invited means emailed or texted."
    if skipped:
        rule += f" Not counted: {', '.join(skipped)}."
    return [line for line in (" ".join(replies), rule) if line]


def parse_as_of(text: str) -> datetime:
    """Read an ISO 8601 timestamp; one without an offset is Los Angeles time."""
    try:
        moment = datetime.fromisoformat(text)
    except ValueError as error:
        raise ValueError(f"--as-of must be an ISO 8601 timestamp, got {text!r}") from error
    return moment if moment.tzinfo else moment.replace(tzinfo=TIME_ZONE)


def format_as_of(moment: datetime) -> str:
    """AP style in Los Angeles time: Nov. 3, 2026, 12:20 p.m. PST."""
    local = moment.astimezone(TIME_ZONE)
    if local.minute == 0 and local.hour in (0, 12):
        clock = "noon" if local.hour == 12 else "midnight"
    else:
        minutes = f":{local.minute:02d}" if local.minute else ""
        clock = f"{local.hour % 12 or 12}{minutes} {'a.m.' if local.hour < 12 else 'p.m.'}"
    return f"{AP_MONTHS[local.month - 1]} {local.day}, {local.year}, {clock} {local.tzname()}"


def load_font(path: Path, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size=size * RENDER_SCALE)
    except OSError as error:
        raise OSError(f"Cannot load font {path}: {error}") from error


def load_fonts() -> Fonts:
    return Fonts(
        headline=load_font(ITALIC_FONT, 29),
        subtitle=load_font(ITALIC_FONT, 17),
        label=load_font(ROMAN_FONT, 17),
        share=load_font(ROMAN_FONT, 15),
        note=load_font(ROMAN_FONT, 14),
    )


def boxes_overlap(first: Sequence[float], second: Sequence[float]) -> bool:
    return first[0] < second[2] and second[0] < first[2] and first[1] < second[3] and second[1] < first[3]


def plan_layout(funnel: Funnel, subtitle: str, fonts: Fonts) -> Layout:
    """Place every text and bar; raise ValueError if any text leaves the canvas or collides."""
    scale = RENDER_SCALE
    draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    rows = stages(funnel)
    title = headline(funnel)
    name_width = max(draw.textlength(stage.name, font=fonts.label) for stage in rows)
    count_width = max(draw.textlength(f"{stage.count:,}", font=fonts.label) for stage in rows)
    share_width = max(draw.textlength(stage.share, font=fonts.share) for stage in rows)
    left = MARGIN * scale
    bar_left = left + name_width + NAME_GAP * scale
    share_left = (WIDTH - MARGIN) * scale - share_width
    count_right = share_left - SHARE_GAP * scale
    bar_right = count_right - count_width - VALUE_GAP * scale
    if bar_right - bar_left < MIN_BAR_AREA * scale:
        raise ValueError("Labels are too wide for the funnel chart")

    # The headline's ink top sits on the top margin; the last note's ink bottom sets the bottom margin.
    y = MARGIN * scale - draw.textbbox((0, 0), title, font=fonts.headline, anchor="ls")[1]
    texts = [Text((left, y), title, fonts.headline, "ls", INK, None)]
    y += SUBTITLE_PITCH * scale
    texts.append(Text((left, y), subtitle, fonts.subtitle, "ls", MUTED, None))
    top = y + ROWS_GAP * scale
    # Row texts share a baseline that centers capitals and figures on the bar.
    cap_height = -draw.textbbox((0, 0), "H", font=fonts.label, anchor="ls")[1]
    bars = []
    for index, stage in enumerate(rows):
        bar_top = top + index * ROW_PITCH * scale
        bars.append(Bar(bar_top, stage.count, stage.parent, stage.color))
        baseline = bar_top + (BAR_HEIGHT * scale + cap_height) / 2
        texts.append(Text((bar_left - NAME_GAP * scale, baseline), stage.name, fonts.label, "rs", INK, None))
        texts.append(Text((count_right, baseline), f"{stage.count:,}", fonts.label, "rs", INK, index))
        if stage.share:
            texts.append(Text((share_left, baseline), stage.share, fonts.share, "ls", MUTED, index))
    y = bars[-1].top + BAR_HEIGHT * scale + NOTES_GAP * scale
    for line in notes(funnel):
        texts.append(Text((left, y), line, fonts.note, "ls", MUTED, None))
        y += NOTE_PITCH * scale
    boxes = [draw.textbbox(text.xy, text.text, font=text.font, anchor=text.anchor) for text in texts]
    height = math.ceil(max(box[3] for box in boxes) / scale) + MARGIN

    canvas = (0, 0, WIDTH * scale, height * scale)
    for text, box in zip(texts, boxes):
        if box[0] < canvas[0] or box[1] < canvas[1] or box[2] > canvas[2] or box[3] > canvas[3]:
            raise ValueError(f"Text runs past the canvas edge: {text.text!r}")
    # Each row's bar area counts as a box too, so no label can sit on a bar or a track.
    tracks = [(bar_left, bar.top, bar_right, bar.top + BAR_HEIGHT * scale) for bar in bars]
    placed = [*((repr(text.text), box) for text, box in zip(texts, boxes)), *(("a bar", track) for track in tracks)]
    for (first, first_box), (second, second_box) in combinations(placed, 2):
        if boxes_overlap(first_box, second_box):
            raise ValueError(f"Labels overlap in the funnel chart: {first} and {second}")
    return Layout(height, bar_left, (bar_right - bar_left) / funnel.invited, bars, texts)


def fade(color: str, amount: float) -> tuple[int, ...]:
    """Blend from the paper background toward `color`."""
    start, end = ImageColor.getrgb(BACKGROUND), ImageColor.getrgb(color)
    amount = min(max(amount, 0.0), 1.0)
    return tuple(round(a + (b - a) * amount) for a, b in zip(start, end))


def render_frame(layout: Layout, overall: float) -> Image.Image:
    scale = RENDER_SCALE
    image = Image.new("RGB", (WIDTH * scale, layout.height * scale), BACKGROUND)
    draw = ImageDraw.Draw(image)
    count = len(layout.bars)
    widths = [bar.count * layout.unit * line_progress(overall, index, count) for index, bar in enumerate(layout.bars)]
    for index, bar in enumerate(layout.bars):
        bottom = bar.top + BAR_HEIGHT * scale
        # A child's track is its parent's bar as drawn now, so each stage grows out of the one before it.
        if bar.parent is not None and widths[bar.parent] > 0:
            draw.rectangle((layout.bar_left, bar.top, layout.bar_left + widths[bar.parent], bottom), fill=TRACK)
        if widths[index] > 0:
            draw.rectangle((layout.bar_left, bar.top, layout.bar_left + widths[index], bottom), fill=bar.color)
    for text in layout.texts:
        color: Any = text.color
        if text.row is not None:
            arrived_at = STAGGER * text.row + 1 - STAGGER * (count - 1)
            color = fade(text.color, (overall - arrived_at) / LABEL_FADE)
        draw.text(text.xy, text.text, fill=color, font=text.font, anchor=text.anchor)
    return image.resize((WIDTH, layout.height), Image.Resampling.LANCZOS)


def render_chart(funnel: Funnel, subtitle: str) -> tuple[bytes, bytes]:
    """Return the GIF, which plays once and holds, and a PNG of its final frame."""
    encoder = find_gifski("outreach funnel animation")
    layout = plan_layout(funnel, subtitle, load_fonts())
    # Run past 1.0 so the last values finish fading in before the final hold.
    end = 1 + LABEL_FADE
    with tempfile.TemporaryDirectory(prefix="outreach-funnel-") as temporary_directory:
        directory = Path(temporary_directory)
        frame_paths = []
        for step in range(MOTION_STEPS + 1):
            frame_path = directory / f"frame-{step:04d}.png"
            frame = render_frame(layout, end * step / MOTION_STEPS)
            frame.save(frame_path, compress_level=1)
            if step == MOTION_STEPS:
                final = io.BytesIO()
                frame.save(final, format="PNG", optimize=True)
            frame.close()
            frame_paths.append(str(frame_path))
        gif = encode_gif(
            encoder,
            frame_paths,
            directory / GIF_NAME,
            width=WIDTH,
            height=layout.height,
            opening_hold=OPENING_HOLD_FRAMES,
            final_hold=FINAL_HOLD_FRAMES,
            repeat=-1,
        )
    return gif, final.getvalue()


def font_faces() -> str:
    faces = ((ROMAN_FONT, "normal", "normal"), (ITALIC_FONT, "normal", "italic"), (BOLD_FONT, "bold", "normal"))
    return "\n".join(
        "@font-face {\n"
        '    font-family: "et-book";\n'
        f'    src: url("data:font/ttf;base64,{base64.b64encode(path.read_bytes()).decode("ascii")}") format("truetype");\n'
        f"    font-weight: {weight};\n"
        f"    font-style: {style};\n"
        "    font-display: swap;\n"
        "}"
        for path, weight, style in faces
    )


def page_css() -> str:
    # Drop the vendored file's comments (they hold its source links); the banner keeps the MIT credits.
    css = re.sub(r"/\*.*?\*/\n?", "", TUFTE_CSS.read_text(encoding="utf-8"), flags=re.DOTALL)
    return f"{LICENSE_BANNER}\n{font_faces()}\n{css.strip()}\n{PAGE_CSS.strip()}"


def lead(funnel: Funnel) -> str:
    sentences = [f"We invited {plural(funnel.invited, 'person', 'people')}."]
    replies = [part for part in (
        f"{funnel.declined:,} declined" if funnel.declined else "",
        f"{funnel.rsvped:,} RSVP’d on Luma" if funnel.rsvped else "",
    ) if part]
    if replies:
        sentences.append(f"Of those, {' and '.join(replies)}.")
    if funnel.rsvped:
        waiting = f"; {funnel.waiting:,} {'is' if funnel.waiting == 1 else 'are'} waiting for approval" if funnel.waiting else ""
        sentences.append(f"Hosts have accepted {funnel.accepted:,} of {plural(funnel.rsvped, 'RSVP')}{waiting}.")
    if funnel.no_reply and replies:
        sentences.append(f"The other {funnel.no_reply:,} {'has' if funnel.no_reply == 1 else 'have'} not replied yet.")
    elif funnel.no_reply:
        sentences.append("None has replied yet.")
    return " ".join(sentences)


def render_page(funnel: Funnel, event: str, as_of: str) -> str:
    rows = stages(funnel)
    alt = (
        f"Animated bar chart of the outreach funnel: {funnel.invited:,} invited, {funnel.declined:,} declined, "
        f"{funnel.rsvped:,} RSVP’d on Luma and {funnel.accepted:,} accepted by hosts."
    )
    rules = (
        f"Invited: we emailed or texted the person. The {EMAIL_SENT} cell holds any text except Bounced.",
        f"Declined: {INVITE_DECLINED} is checked.",
        f"RSVP’d: {LUMA_RSVP} is checked. The person registered on the Luma event page.",
        f"Accepted: {LUMA_ACCEPT} is checked. A host approved the registration on Luma.",
        f"Not counted: bounced emails ({EMAIL_SENT} says Bounced) and people not yet contacted "
        f"({EMAIL_SENT} is blank). Blank rows are skipped.",
        "Shares are whole percents; halves round up.",
    )
    items = "\n".join(f"<li>{html.escape(rule)}</li>" for rule in rules)
    table = "\n".join(
        f'<tr><td>{html.escape(stage.name)}</td><td class="number">{stage.count:,}</td>'
        f"<td>{html.escape(stage.share)}</td></tr>"
        for stage in rows
    )
    title = html.escape(f"{event}: outreach funnel")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
{page_css()}
</style>
</head>
<body>
<article>
<h1>{title}</h1>
<p class="subtitle">as of {html.escape(as_of)}</p>
<section>
<p>{html.escape(lead(funnel))}</p>
<figure>
<label for="scale-note" class="margin-toggle">&#8853;</label><input type="checkbox" id="scale-note" class="margin-toggle"><span class="marginnote">Every bar shares one scale that starts at zero. The faint bar behind each stage is the group it is counted from.</span>
<img src="{GIF_NAME}" alt="{html.escape(alt)}">
</figure>
</section>
<section>
<h2>How we count</h2>
<ul>
{items}
</ul>
<table>
<thead><tr><th>Stage</th><th class="number">People</th><th>Share</th></tr></thead>
<tbody>
{table}
</tbody>
</table>
</section>
</article>
</body>
</html>
"""


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sheet", type=Path, required=True, help="CSV download, or gog sheets get --json output (.json)")
    parser.add_argument("--event", required=True, help='event name, for example "Nov. 12 After Hours"')
    parser.add_argument("--as-of", help="ISO 8601 export time (default: the export file's modification time)")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DIR, help="where to write the GIF, PNG and index.html")
    args = parser.parse_args(argv)
    try:
        funnel = count_funnel(read_sheet(args.sheet))
        moment = parse_as_of(args.as_of) if args.as_of else datetime.fromtimestamp(args.sheet.stat().st_mtime, TIME_ZONE)
        as_of = format_as_of(moment)
        gif, png = render_chart(funnel, f"{args.event} outreach, as of {as_of}")
        outputs = {
            args.output_dir / GIF_NAME: gif,
            args.output_dir / PNG_NAME: png,
            args.output_dir / PAGE_NAME: render_page(funnel, args.event, as_of).encode("utf-8"),
        }
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for path, content in outputs.items():
            path.write_bytes(content)
            print(f"Wrote {path}")
    except (SheetError, ValueError, AnimationError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
