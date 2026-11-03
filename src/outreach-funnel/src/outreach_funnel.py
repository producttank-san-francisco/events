#!/usr/bin/env python3
"""Render an event's outreach funnel by role as an interactive d3-sankey web page."""

from __future__ import annotations

import argparse
import base64
import csv
import html
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime
from fractions import Fraction
from pathlib import Path
from typing import Any, NamedTuple, Sequence
from zoneinfo import ZoneInfo

MODULE_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DIR = REPO_ROOT / "docs" / "reports" / "outreach-funnel"
ASSETS = MODULE_ROOT / "assets"
TUFTE_CSS = ASSETS / "tufte.css"
ROMAN_FONT = ASSETS / "et-book" / "et-book-roman-line-figures.ttf"
ITALIC_FONT = ASSETS / "et-book" / "et-book-display-italic-old-style-figures.ttf"
BOLD_FONT = ASSETS / "et-book" / "et-book-bold-line-figures.ttf"
# (script, its license) in load order; the chart code needs d3 and d3-sankey first.
SCRIPTS = (
    (ASSETS / "d3" / "d3.min.js", ASSETS / "d3" / "d3-LICENSE"),
    (ASSETS / "d3" / "d3-sankey.min.js", ASSETS / "d3" / "d3-sankey-LICENSE"),
    (ASSETS / "outreach-sankey.js", None),
)
TIME_ZONE = ZoneInfo("America/Los_Angeles")
AP_MONTHS = ("Jan.", "Feb.", "March", "April", "May", "June", "July", "Aug.", "Sept.", "Oct.", "Nov.", "Dec.")
PAGE_NAME = "index.html"

NAME = "Name"
EMAIL = "Email"
LABEL = "Label"
EMAIL_SENT = "Email Sent"
INVITE_DECLINED = "Invite Declined"
LUMA_RSVP = "Luma RSVP"
LUMA_ACCEPT = "Luma Accept"
REQUIRED_COLUMNS = (NAME, EMAIL, LABEL, EMAIL_SENT, INVITE_DECLINED, LUMA_RSVP, LUMA_ACCEPT)
LUMA_COLUMNS = ("name", "email", "approval_status")

VIA_LUMA = "Via Luma only"
VOLUNTEERS = "Volunteers"
SPEAKERS = "Speakers"
SPONSORS = "Sponsors"
JUDGES = "Judges & partners"
RSVPD = "RSVP’d"
DECLINED = "Declined"
NO_REPLY = "No reply yet"
ACCEPTED = "Accepted"
WAITING = "Waiting for host"
HOST_DECLINED = "Host declined"
REPLIES = (RSVPD, DECLINED, NO_REPLY)
DECISIONS = (ACCEPTED, WAITING, HOST_DECLINED)
# A ribbon's strength follows where it ends: active RSVPs stand out, the rest stay light.
TIERS = {RSVPD: "strong", ACCEPTED: "strong", WAITING: "mid", DECLINED: "faint", NO_REPLY: "faint", HOST_DECLINED: "faint"}
LUMA_STAGES = {"approved": ACCEPTED, "pending_approval": WAITING, "declined": HOST_DECLINED}

INK = "#262421"


class Role(NamedTuple):
    name: str
    color: str
    noun: str  # plural, for tooltips: "35% of 20 invited volunteers"


# Flow order: the top row of the chart, left to right.
ROLES = (
    Role(VIA_LUMA, "#8c877a", "guests via Luma only"),
    Role(VOLUNTEERS, "#288c78", "volunteers"),
    Role(SPEAKERS, "#c45a69", "speakers"),
    Role(SPONSORS, "#3c69aa", "sponsors"),
    Role(JUDGES, "#a09632", "judges & partners"),
)
TABLE_ORDER = (SPEAKERS, SPONSORS, VOLUNTEERS, JUDGES, VIA_LUMA)

PAGE_CSS = """
figure.funnel { max-width: 1060px; position: relative; }
figure.funnel svg { display: block; width: 100%; height: auto; }
.funnel text { font-family: et-book, Palatino, "Palatino Linotype", "Palatino LT STD", "Book Antiqua", Georgia, serif; }
.funnel .ribbon, .funnel .segment { transition: fill-opacity 150ms, stroke-opacity 150ms, opacity 150ms; }
.funnel [tabindex] { outline: none; cursor: pointer; }
.funnel .ribbon:focus-visible { stroke: #262421; stroke-width: 2px; stroke-opacity: 1 !important; }
.funnel .ring { fill: none; stroke: none; }
.funnel .node:focus-visible .ring, .funnel .table-row:focus-visible .ring { stroke: #262421; stroke-width: 1.5px; }
.funnel .table-row.pinned text { font-weight: bold; }
.funnel-tip { position: fixed; z-index: 10; pointer-events: none; max-width: 22rem; padding: 0.5rem 0.75rem; background: #fffff8; border: 1px solid #262421; font-size: 1.2rem; line-height: 1.5; }
.funnel-tip[hidden] { display: none; }
.funnel-tip b { font-weight: bold; }
@media (prefers-reduced-motion: reduce) { .funnel .ribbon, .funnel .segment { transition: none; } }
@media (max-width: 760px) {
    figure.funnel { max-width: 100%; overflow-x: auto; }
    figure.funnel svg { min-width: 760px; }
}
"""
LICENSE_BANNER = (
    "/* tufte-css: Copyright (c) 2014 Dave Liepmann, MIT License. "
    "ET Book: Copyright (c) 2015 Dmitry Krasny, Bonnie Scranton, Edward Tufte, MIT License. */"
)


class SheetError(ValueError):
    """The sheet export cannot be counted as it stands; the message says what to fix."""


class LumaError(ValueError):
    """The Luma guest export cannot be used as it stands; the message says what to fix."""


class Invitee(NamedTuple):
    row: int  # sheet row number, counting the header as row 1
    name: str
    email: str
    role: str
    declined: bool  # Invite Declined is checked
    rsvp: bool  # the sheet's Luma RSVP checkbox
    accept: bool  # the sheet's Luma Accept checkbox


class Outreach(NamedTuple):
    invitees: list[Invitee]
    bounced: int
    not_contacted: int


class Guest(NamedTuple):
    name: str
    email: str
    status: str  # Luma approval_status


class NameMatch(NamedTuple):
    row: int
    sheet_name: str
    luma_name: str


class Matching(NamedTuple):
    guests: dict[int, Guest]  # sheet row number -> its Luma guest
    unused: list[Guest]  # guests no invitee matches: "Via Luma only"
    by_email: int
    by_name: list[NameMatch]


def read_csv(path: Path) -> list[list[str]]:
    with path.open(newline="", encoding="utf-8-sig") as file:
        return list(csv.reader(file))


def read_sheet(path: Path) -> list[list[str]]:
    """Read a CSV download, or the JSON that `gog sheets get <id> <range> --json` prints."""
    if path.suffix.lower() != ".json":
        return read_csv(path)
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


def role_of(label: str) -> str | None:
    """The role named by the first `;`-separated entry of a Label cell, or None if it names no role."""
    first = label.split(";")[0].strip()
    if first.startswith("Speaker"):
        return SPEAKERS
    if first.startswith("Volunteer"):
        return VOLUNTEERS
    if "sponsor" in first.lower():
        return SPONSORS
    if first in ("Judge", "Community Partner"):
        return JUDGES
    return None


def count_outreach(rows: Sequence[Sequence[str]]) -> Outreach:
    if not rows:
        raise SheetError("The sheet export is empty")
    header = [name.strip() for name in rows[0]]
    missing = [column for column in REQUIRED_COLUMNS if column not in header]
    if missing:
        raise SheetError(f"The sheet is missing column{'s' if len(missing) > 1 else ''}: {', '.join(missing)}")
    columns = {column: header.index(column) for column in REQUIRED_COLUMNS}
    problems: list[str] = []
    invitees: list[Invitee] = []
    invited = bounced = not_contacted = 0
    for row_number, row in enumerate(rows[1:], start=2):
        cells = [*row, *[""] * (len(header) - len(row))]
        if not any(cell.strip() for cell in cells):
            continue
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
        not_contacted += not sent
        if not is_invited:
            continue
        label = cells[columns[LABEL]]
        role = role_of(label)
        if role is None:
            first = label.split(";")[0].strip()
            named = f"{first!r} is not a role" if first else "blank"
            problems.append(
                f"row {row_number}, {LABEL}: {named}; the first label must start with Speaker or Volunteer, "
                "contain Sponsor, or be Judge or Community Partner"
            )
            continue
        invitees.append(Invitee(
            row_number, cells[columns[NAME]].strip(), cells[columns[EMAIL]].strip(), role, said_no, rsvp, accept,
        ))
    if problems:
        heading = "The sheet has 1 problem" if len(problems) == 1 else f"The sheet has {len(problems)} problems"
        raise SheetError(f"{heading}; fix and export again:\n" + "\n".join(f"  {problem}" for problem in problems))
    if invited == 0:
        raise SheetError(f"Nobody is invited yet ({EMAIL_SENT} is blank or Bounced on every row): nothing to chart")
    return Outreach(invitees, bounced, not_contacted)


def luma_guests(rows: Sequence[Sequence[str]]) -> list[Guest]:
    """Read the rows of a Luma guest CSV export, header first."""
    if not rows:
        raise LumaError("The Luma export is empty")
    header = [name.strip() for name in rows[0]]
    missing = [column for column in LUMA_COLUMNS if column not in header]
    if missing:
        raise LumaError(f"The Luma export is missing column{'s' if len(missing) > 1 else ''}: {', '.join(missing)}")
    name, email, status = (header.index(column) for column in LUMA_COLUMNS)
    guests = []
    for row in rows[1:]:
        cells = [*row, *[""] * (len(header) - len(row))]
        if any(cell.strip() for cell in cells):
            guests.append(Guest(cells[name].strip(), cells[email].strip(), cells[status].strip()))
    unknown = Counter(guest.status for guest in guests if guest.status not in LUMA_STAGES)
    if unknown:
        listed = ", ".join(f"{status!r} ({plural(count, 'guest')})" for status, count in unknown.items())
        raise LumaError(f"The Luma export has an unknown approval_status: {listed}")
    return guests


def name_key(name: str) -> tuple[str, str] | None:
    """First and last word of a name, lowercased, with every character but a-z and spaces dropped."""
    words = re.sub(r"[^a-z ]", "", name.lower()).split()
    return (words[0], words[-1]) if words else None


def match_guests(invitees: Sequence[Invitee], guests: Sequence[Guest]) -> Matching:
    """Match each invitee to at most one guest: by email first, then by first and last name."""
    used = [False] * len(guests)
    matched: dict[int, Guest] = {}
    for invitee in invitees:
        email = invitee.email.strip().lower()
        if not email:
            continue
        for index, guest in enumerate(guests):
            if not used[index] and guest.email.strip().lower() == email:
                used[index] = True
                matched[invitee.row] = guest
                break
    by_email = len(matched)
    by_name = []
    for invitee in invitees:
        key = name_key(invitee.name)
        if invitee.row in matched or key is None:
            continue
        candidates = [index for index, guest in enumerate(guests) if not used[index] and name_key(guest.name) == key]
        if len(candidates) > 1:
            raise LumaError(
                f"ambiguous name match for sheet row {invitee.row}: {len(candidates)} Luma guests share its first "
                "and last name; add the guest's Luma email to the sheet"
            )
        if candidates:
            guest = guests[candidates[0]]
            used[candidates[0]] = True
            matched[invitee.row] = guest
            by_name.append(NameMatch(invitee.row, invitee.name, guest.name))
    unused = [guest for index, guest in enumerate(guests) if not used[index]]
    return Matching(matched, unused, by_email, by_name)


def disagreements(invitees: Sequence[Invitee], matching: Matching) -> list[int]:
    """Sheet rows whose Luma RSVP or Luma Accept checkbox disagrees with the Luma export."""
    rows = []
    for invitee in invitees:
        guest = matching.guests.get(invitee.row)
        if invitee.rsvp != (guest is not None) or invitee.accept != (guest is not None and guest.status == "approved"):
            rows.append(invitee.row)
    return rows


def stages_of(invitee: Invitee, guest: Guest | None) -> tuple[str, str | None]:
    """An invitee's reply and, for an RSVP, the host's decision. Luma is the record."""
    if guest is not None:
        return RSVPD, LUMA_STAGES[guest.status]
    return (DECLINED if invitee.declined else NO_REPLY), None


def plural(count: int, singular: str, plural_form: str | None = None) -> str:
    return f"{count:,} {singular if count == 1 else plural_form or singular + 's'}"


def percent(part: int, whole: int) -> int:
    """Whole percent of the exact fraction, with halves rounded up."""
    return math.floor(Fraction(100 * part, whole) + Fraction(1, 2))


def ink(color: str) -> str:
    """Text color for a role: 75% of the role color mixed with 25% ink."""
    mixed = (round(i + (c - i) * 0.75) for c, i in zip(bytes.fromhex(color[1:]), bytes.fromhex(INK[1:])))
    return "#" + "".join(f"{channel:02x}" for channel in mixed)


def footnotes(invited: int, matching: Matching, mismatches: int, bounced: int, not_contacted: int) -> list[str]:
    matched = len(matching.guests)
    if mismatches:
        verdict = f"{plural(mismatches, 'sheet row')} {'disagrees' if mismatches == 1 else 'disagree'} with Luma; the chart uses Luma."
    elif matched == 1:
        verdict = "the 1 invitee RSVP agrees with the sheet."
    elif matched:
        verdict = f"all {matched:,} invitee RSVPs agree with the sheet."
    else:
        verdict = "no invitee has RSVP’d, and the sheet agrees."
    skipped = [part for count, part in (
        (bounced, plural(bounced, "bounced email")),
        (not_contacted, f"{plural(not_contacted, 'person', 'people')} not yet contacted"),
    ) if count]
    roles = "Role = first Label in the sheet; all sponsor labels count as Sponsors."
    return [
        f"Luma guest export matched to the outreach sheet by email ({matching.by_email:,}), "
        f"then by name ({len(matching.by_name):,}): {verdict}",
        f"{roles} Not drawn: {', '.join(skipped)}." if skipped else roles,
        f"Hosts approve RSVPs on Luma. Of {plural(invited, 'invitee')}, {matched:,} RSVP’d.",
    ]


def funnel_data(outreach: Outreach, matching: Matching, as_of: str) -> dict[str, Any]:
    """Everything the page draws: nodes, links with their strength tier, labels and the role table."""
    people = [(invitee.role, *stages_of(invitee, matching.guests.get(invitee.row))) for invitee in outreach.invitees]
    people += [(VIA_LUMA, RSVPD, LUMA_STAGES[guest.status]) for guest in matching.unused]
    sizes = Counter(role for role, _, _ in people)
    replies = Counter((role, reply) for role, reply, _ in people)
    decisions = Counter((role, decision) for role, _, decision in people if decision)
    reply_totals = Counter(reply for _, reply, _ in people)
    decision_totals = Counter(decision for _, _, decision in people if decision)
    roles = [role for role in ROLES if sizes[role.name]]
    invited = len(outreach.invitees)
    via = sizes[VIA_LUMA]
    rsvped = reply_totals[RSVPD]

    lines = {
        VIA_LUMA: ["Via Luma only", f"{via:,}, not invited"],
        **{role.name: [f"{role.name} {sizes[role.name]:,}"] for role in roles if role.name != VIA_LUMA},
        RSVPD: [f"RSVP’d {rsvped:,}", f"{rsvped - via:,} invited", f"{via:,} via Luma"],
        DECLINED: [f"Declined {reply_totals[DECLINED]:,}"],
        NO_REPLY: [f"No reply yet {reply_totals[NO_REPLY]:,}", f"{percent(reply_totals[NO_REPLY], invited)}% of invited"],
    }
    for decision, share_of in ((ACCEPTED, "% of RSVPs"), (WAITING, "%"), (HOST_DECLINED, "%")):
        if rsvped:
            count = decision_totals[decision]
            lines[decision] = [f"{decision} {count:,}", f"{percent(count, rsvped)}{share_of}"]
    nodes = [{"name": role.name, "stage": 0, "lines": lines[role.name]} for role in roles]
    nodes += [{"name": reply, "stage": 1, "lines": lines[reply]} for reply in REPLIES if reply_totals[reply]]
    nodes += [{"name": decision, "stage": 2, "lines": lines[decision]} for decision in DECISIONS if decision_totals[decision]]

    # Role by role into the replies, then decision by decision out of RSVP'd: d3-sankey keeps this order.
    links = [
        {"source": role.name, "target": reply, "role": role.name, "value": replies[role.name, reply],
         "tier": TIERS[reply], "share": percent(replies[role.name, reply], sizes[role.name])}
        for role in roles for reply in REPLIES if replies[role.name, reply]
    ]
    links += [
        {"source": RSVPD, "target": decision, "role": role.name, "value": decisions[role.name, decision],
         "tier": TIERS[decision], "share": percent(decisions[role.name, decision], replies[role.name, RSVPD])}
        for decision in DECISIONS for role in roles if decisions[role.name, decision]
    ]
    mismatches = len(disagreements(outreach.invitees, matching))
    accepted = decision_totals[ACCEPTED]
    return {
        "headline": f"RSVPs by role: {rsvped:,} on Luma, {accepted:,} accepted",
        "subline": f"width = people · color = role · as of {as_of}",
        "notes": footnotes(invited, matching, mismatches, outreach.bounced, outreach.not_contacted),
        "roles": [
            {"name": role.name, "color": role.color, "ink": ink(role.color), "noun": role.noun,
             "invited": None if role.name == VIA_LUMA else sizes[role.name], "total": sizes[role.name],
             "rsvped": replies[role.name, RSVPD], "accepted": decisions[role.name, ACCEPTED]}
            for role in roles
        ],
        "table": [name for name in TABLE_ORDER if sizes[name]],
        "nodes": nodes,
        "links": links,
        "totals": {
            "invited": invited, "via_luma": via, "rsvped": rsvped, "accepted": accepted,
            "declined": reply_totals[DECLINED], "no_reply": reply_totals[NO_REPLY],
            "waiting": decision_totals[WAITING], "host_declined": decision_totals[HOST_DECLINED],
        },
        "bounced": outreach.bounced,
        "not_contacted": outreach.not_contacted,
        "matched": {"email": matching.by_email, "name": len(matching.by_name)},
        "mismatches": mismatches,
        "as_of": as_of,
    }


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


def scripts() -> str:
    """d3, d3-sankey and the chart code, each license text in a comment above its script."""
    tags = []
    for script, license_file in SCRIPTS:
        notice = f"/*\n{license_file.read_text(encoding='utf-8').strip()}\n*/\n" if license_file else ""
        tags.append(f"<script>\n{notice}{script.read_text(encoding='utf-8').strip()}\n</script>")
    return "\n".join(tags)


def render_page(data: dict[str, Any], event: str) -> str:
    totals = data["totals"]
    label = (
        f"Sankey chart, {data['headline']}. {totals['invited']:,} invited and {totals['via_luma']:,} via Luma only, "
        "flowing from role to reply to host decision; ribbon width is people. "
        "Hover or tab to a ribbon or bar to read its people. Click a role, or press Enter on it, to pin it; "
        "press Escape to clear."
    )
    rules = (
        f"Invited: the {EMAIL_SENT} cell holds any text except Bounced. Bounced emails and people not yet contacted "
        f"({EMAIL_SENT} is blank) are not drawn; the footnote counts them. Blank rows are skipped.",
        f"Role: the first entry in the {LABEL} cell. Speaker means Speakers, Volunteer means Volunteers, any label "
        "with Sponsor in it means Sponsors, and Judge or Community Partner means Judges & partners.",
        "Each invitee is matched to a Luma guest by email first, then by first and last name. "
        "A guest matches one invitee at most.",
        "A matched invitee RSVP’d. Luma says what the host decided: approved is Accepted, pending approval is "
        "Waiting for host and declined is Host declined.",
        f"An invitee with no Luma match declined if {INVITE_DECLINED} is checked; otherwise there is no reply yet.",
        "Luma guests who match no invitee were not invited: they are “Via Luma only” and are placed by their "
        "Luma status in the same way.",
        f"The sheet’s {LUMA_RSVP} and {LUMA_ACCEPT} checkboxes are compared with Luma. Where they disagree, "
        "the chart uses Luma.",
        "Shares are whole percents; halves round up.",
    )
    items = "\n".join(f"<li>{html.escape(rule)}</li>" for rule in rules)
    embedded = json.dumps(data, ensure_ascii=False).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
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
<h1>{html.escape(event)}</h1>
<p class="subtitle">as of {html.escape(data["as_of"])}</p>
<section>
<figure class="funnel">
<svg id="funnel-chart" viewBox="0 0 1060 1040" role="group" aria-label="{html.escape(label)}"></svg>
<div id="funnel-tip" class="funnel-tip" role="tooltip" hidden></div>
</figure>
</section>
<section>
<h2>How we count</h2>
<ul>
{items}
</ul>
</section>
</article>
<script type="application/json" id="funnel-data">{embedded}</script>
{scripts()}
</body>
</html>
"""


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sheet", type=Path, required=True, help="CSV download, or gog sheets get --json output (.json)")
    parser.add_argument("--luma", type=Path, required=True, help="Luma guest CSV export")
    parser.add_argument("--event", required=True, help='event name, for example "Nov. 12 After Hours"')
    parser.add_argument("--as-of", help="ISO 8601 export time (default: the older of the two files' modification times)")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DIR, help="where to write index.html")
    args = parser.parse_args(argv)
    try:
        outreach = count_outreach(read_sheet(args.sheet))
        matching = match_guests(outreach.invitees, luma_guests(read_csv(args.luma)))
        if args.as_of:
            moment = parse_as_of(args.as_of)
        else:
            # The chart is no newer than its older input.
            moment = datetime.fromtimestamp(min(args.sheet.stat().st_mtime, args.luma.stat().st_mtime), TIME_ZONE)
        page = render_page(funnel_data(outreach, matching, format_as_of(moment)), args.event)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        path = args.output_dir / PAGE_NAME
        path.write_text(page, encoding="utf-8")
    except (SheetError, LumaError, ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Wrote {path}")
    for row in disagreements(outreach.invitees, matching):
        print(f"warning: sheet row {row}: {LUMA_RSVP} or {LUMA_ACCEPT} disagrees with Luma; the chart uses Luma", file=sys.stderr)
    if matching.by_name:
        print("Matched by name, please check:")
        for match in matching.by_name:
            print(f"  row {match.row}: {match.sheet_name} (sheet) = {match.luma_name} (Luma)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
