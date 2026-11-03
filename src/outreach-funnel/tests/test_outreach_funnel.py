import csv
import io
import json
import os
import re
import sys
import tempfile
import unittest
from collections import Counter
from contextlib import redirect_stderr, redirect_stdout
from itertools import groupby
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.outreach_funnel import (
    LumaError, SheetError, count_outreach, format_as_of, funnel_data, luma_guests, main, match_guests, parse_as_of,
    percent, read_sheet, render_page, role_of,
)

HEADER = ["Name", " Email", "Label", " Email Sent", "Invite Declined", "Luma RSVP ", "Luma Accept", "Notes"]
LUMA_HEADER = ["api_id", "name", "email", "approval_status", "ticket_name"]
AS_OF = "Nov. 3, 2026, noon PST"


def person(name, email="", label="Speaker", sent="1", declined="", rsvp="", accept="", notes=""):
    return [name, email, label, sent, declined, rsvp, accept, notes]


def guest(name, email, status):
    return ["gst-1", name, email, status, "Standard"]


# Made-up people. Rows 2-7 are invited; row 8 bounced; row 9 not contacted.
SHEET = [
    HEADER,
    person("Person One", "person1@example.com", "Speaker; Sponsor champion", rsvp="TRUE", accept="TRUE"),
    person("Person Two", "person2@example.com", "Volunteer", rsvp="TRUE"),
    person("Person Three", "", "Sponsor support", rsvp="TRUE"),
    person("Person Four", "person4@example.com", "Judge", declined="TRUE"),
    person("Person Five", "person5@example.com", "Community Partner"),
    person("Person Six", "person6@example.com", "Alum/Sponsor"),
    person("Person Seven", "person7@example.com", sent="Bounced"),
    person("Person Eight", "person8@example.com", sent=""),
]
LUMA = [
    LUMA_HEADER,
    guest("Person One", " Person1@Example.com ", "approved"),
    guest("Person Two", "person2@example.com", "pending_approval"),
    guest("Person Q. Three", "person3@elsewhere.example.com", "declined"),
    guest("Guest Alpha", "alpha@example.com", "approved"),
    guest("Guest Beta", "beta@example.com", "pending_approval"),
]


def write_csv(path, rows, encoding="utf-8"):
    with path.open("w", newline="", encoding=encoding) as file:
        csv.writer(file).writerows(rows)


def chart(sheet_rows, luma_rows):
    outreach = count_outreach(sheet_rows)
    return funnel_data(outreach, match_guests(outreach.invitees, luma_guests(luma_rows)), AS_OF)


def flows(data):
    return {(link["source"], link["target"], link["role"]): link["value"] for link in data["links"]}


class SheetTest(unittest.TestCase):
    def test_bounced_and_not_contacted_are_counted(self):
        rows = [
            HEADER,
            person("Person 1", sent="1"),
            person("Person 2", sent="Host text"),
            person("Person 3", sent=" bounced "),
            person("Person 4", sent=""),
            ["", " ", "", "", "", "", "", ""],
            person("Person 5", sent="1"),
        ]
        outreach = count_outreach(rows)
        self.assertEqual([invitee.row for invitee in outreach.invitees], [2, 3, 7])
        self.assertEqual((outreach.bounced, outreach.not_contacted), (1, 1))

    def test_inconsistent_rows_are_all_reported(self):
        rows = [
            HEADER,
            person("Person 1", rsvp="TRUE", accept="TRUE"),
            person("Person 2", accept="TRUE"),
            person("Person 3", sent="", rsvp="TRUE"),
            person("Person 4", declined="TRUE", rsvp="TRUE"),
            person("Person 5", declined="yes"),
        ]
        with self.assertRaises(SheetError) as caught:
            count_outreach(rows)
        message = str(caught.exception)
        for row_number in (3, 4, 5, 6):
            self.assertRegex(message, rf"\brow {row_number}\b")
        self.assertNotRegex(message, r"\brow 2\b")

    def test_missing_columns_are_named(self):
        with self.assertRaises(SheetError) as caught:
            count_outreach([["Name", "Email Sent", "Invite Declined"], ["Person 1", "1", ""]])
        for column in ("Email", "Label", "Luma RSVP", "Luma Accept"):
            self.assertIn(column, str(caught.exception))

    def test_nobody_invited_is_refused(self):
        with self.assertRaises(SheetError):
            count_outreach([HEADER, person("Person 1", sent="Bounced"), person("Person 2", sent="")])

    def test_gog_json_and_csv_exports_count_the_same(self):
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "outreach.csv"
            json_path = Path(directory) / "outreach.json"
            write_csv(csv_path, SHEET)
            # gog drops trailing blank cells, so most rows are shorter than the header.
            trimmed = [row[: max((i + 1 for i, cell in enumerate(row) if cell), default=0)] for row in SHEET]
            json_path.write_text(json.dumps({"range": "Sheet1!A1:H9", "values": trimmed}))
            self.assertLess(len(trimmed[1]), len(HEADER))
            self.assertEqual(count_outreach(read_sheet(json_path)), count_outreach(read_sheet(csv_path)))
            self.assertEqual(len(count_outreach(read_sheet(json_path)).invitees), 6)

    def test_role_comes_from_the_first_label(self):
        cases = {
            "Speaker; Sponsor champion": "Speakers",
            "Speaker - panel": "Speakers",
            "Volunteer lead; Speaker": "Volunteers",
            "Alum/Sponsor": "Sponsors",
            "sponsor contact unknown": "Sponsors",
            " Sponsor prospect ; Judge": "Sponsors",
            "Judge": "Judges & partners",
            "Community Partner; Volunteer": "Judges & partners",
        }
        for label, role in cases.items():
            with self.subTest(label=label):
                self.assertEqual(role_of(label), role)

    def test_unknown_or_blank_label_is_refused(self):
        rows = [
            HEADER,
            person("Person 1", label="Friend; Speaker"),
            person("Person 2", label=" "),
            person("Person 3", label="", sent="Bounced"),
            person("Person 4", label="Speaker"),
        ]
        with self.assertRaises(SheetError) as caught:
            count_outreach(rows)
        message = str(caught.exception)
        self.assertRegex(message, r"\brow 2\b.*Friend")
        self.assertRegex(message, r"\brow 3\b")
        self.assertNotRegex(message, r"\brow [45]\b")


class LumaTest(unittest.TestCase):
    def test_email_match_runs_before_name_match(self):
        # Row 2 would take the guest by name if name matching ran row by row with email matching.
        outreach = count_outreach([
            HEADER,
            person("Person One", "other@example.com"),
            person("P. One", "Person1@Example.com "),
        ])
        matching = match_guests(outreach.invitees, luma_guests([LUMA_HEADER, guest("Person One", "person1@example.com", "approved")]))
        self.assertEqual(list(matching.guests), [3])
        self.assertEqual((matching.by_email, matching.by_name), (1, []))

    def test_name_match_uses_first_and_last_word(self):
        outreach = count_outreach([HEADER, person("person  one."), person("Person Two")])
        guests = luma_guests([
            LUMA_HEADER, guest("PERSON Q. O'NE", "a@example.com", "approved"), guest("Person Three", "b@example.com", "approved"),
        ])
        matching = match_guests(outreach.invitees, guests)
        self.assertEqual(list(matching.guests), [2])
        self.assertEqual([tuple(match) for match in matching.by_name], [(2, "person  one.", "PERSON Q. O'NE")])
        self.assertEqual([guest.name for guest in matching.unused], ["Person Three"])

    def test_ambiguous_name_match_is_refused(self):
        outreach = count_outreach([HEADER, person("Person One")])
        guests = luma_guests([
            LUMA_HEADER, guest("Person One", "a@example.com", "approved"), guest("Person A. One", "b@example.com", "declined"),
        ])
        with self.assertRaisesRegex(LumaError, "ambiguous name match for sheet row 2"):
            match_guests(outreach.invitees, guests)

    def test_unmatched_guests_count_as_via_luma_only(self):
        data = chart(SHEET, LUMA)
        via = next(role for role in data["roles"] if role["name"] == "Via Luma only")
        self.assertEqual((via["invited"], via["total"], via["rsvped"], via["accepted"]), (None, 2, 2, 1))
        self.assertEqual((data["totals"]["invited"], data["totals"]["via_luma"]), (6, 2))
        self.assertEqual(flows(data)["Via Luma only", "RSVP’d", "Via Luma only"], 2)
        self.assertEqual(data["matched"], {"email": 2, "name": 1})

    def test_luma_status_sets_the_stage(self):
        rows = [
            HEADER,
            person("Person 1", "person1@example.com", rsvp="TRUE", accept="TRUE"),
            person("Person 2", "person2@example.com", rsvp="TRUE"),
            person("Person 3", "person3@example.com", rsvp="TRUE"),
            # Luma is the record: an RSVP on Luma beats a checked Invite Declined.
            person("Person 4", "person4@example.com", declined="TRUE"),
        ]
        luma = [
            LUMA_HEADER,
            guest("Person 1", "person1@example.com", "approved"),
            guest("Person 2", "person2@example.com", "pending_approval"),
            guest("Person 3", "person3@example.com", "declined"),
            guest("Person 4", "person4@example.com", "approved"),
        ]
        totals = chart(rows, luma)["totals"]
        self.assertEqual(
            (totals["rsvped"], totals["declined"], totals["accepted"], totals["waiting"], totals["host_declined"]),
            (4, 0, 2, 1, 1),
        )

    def test_unknown_luma_status_is_refused(self):
        rows = [LUMA_HEADER, guest("Guest 1", "g1@example.com", "invited"), guest("Guest 2", "g2@example.com", "invited")]
        with self.assertRaisesRegex(LumaError, r"'invited' \(2 guests\)"):
            luma_guests(rows)

    def test_missing_luma_column_is_refused(self):
        with self.assertRaisesRegex(LumaError, "approval_status"):
            luma_guests([["api_id", "name", "email"], ["gst-1", "Guest 1", "g1@example.com"]])

    def test_sheet_disagreement_is_counted(self):
        data = chart([HEADER, person("Person 1", "person1@example.com", rsvp="TRUE")], [LUMA_HEADER])
        self.assertEqual(data["mismatches"], 1)
        self.assertEqual((data["totals"]["rsvped"], data["totals"]["no_reply"]), (0, 1))
        self.assertIn("1 sheet row disagrees with Luma; the chart uses Luma", data["notes"][0])

        agreeing = chart(SHEET, LUMA)
        self.assertEqual(agreeing["mismatches"], 0)
        self.assertIn("All 3 agreed with the outreach sheet", agreeing["notes"][0])


class FlowTest(unittest.TestCase):
    def test_every_node_keeps_its_people(self):
        data = chart(SHEET, LUMA)
        inflow, outflow = Counter(), Counter()
        for link in data["links"]:
            self.assertGreater(link["value"], 0)
            outflow[link["source"]] += link["value"]
            inflow[link["target"]] += link["value"]
        for node in data["nodes"]:
            with self.subTest(node=node["name"]):
                self.assertGreater(inflow[node["name"]] + outflow[node["name"]], 0)
                if node["stage"] == 1 and outflow[node["name"]]:
                    self.assertEqual(inflow[node["name"]], outflow[node["name"]])
        tops = {node["name"]: outflow[node["name"]] for node in data["nodes"] if node["stage"] == 0}
        self.assertEqual(
            tops, {"Via Luma only": 2, "Volunteers": 1, "Speakers": 1, "Sponsors": 2, "Judges & partners": 2},
        )
        self.assertEqual(
            {node["name"]: inflow[node["name"]] for node in data["nodes"] if node["stage"] > 0},
            {"RSVP’d": 5, "Declined": 1, "No reply yet": 2, "Accepted": 2, "Waiting for host": 2, "Host declined": 1},
        )

    def test_link_tiers_follow_the_destination(self):
        expected = {
            "RSVP’d": "strong", "Accepted": "strong", "Waiting for host": "mid",
            "Declined": "faint", "No reply yet": "faint", "Host declined": "faint",
        }
        links = chart(SHEET, LUMA)["links"]
        self.assertEqual({link["target"] for link in links}, set(expected))
        for link in links:
            with self.subTest(link=(link["source"], link["target"], link["role"])):
                self.assertEqual(link["tier"], expected[link["target"]])

    def test_bands_leave_rsvpd_in_the_role_order_they_enter(self):
        # d3-sankey keeps link order, so decision-first bands would leave RSVP’d under another role's segment.
        rows = [
            HEADER,
            person("Person 1", "person1@example.com", "Volunteer", rsvp="TRUE", accept="TRUE"),
            person("Person 2", "person2@example.com", "Volunteer", rsvp="TRUE"),
            person("Person 3", "person3@example.com", "Speaker", rsvp="TRUE", accept="TRUE"),
            person("Person 4", "person4@example.com", "Speaker", rsvp="TRUE"),
        ]
        luma = [
            LUMA_HEADER,
            guest("Person 1", "person1@example.com", "approved"),
            guest("Person 2", "person2@example.com", "declined"),
            guest("Person 3", "person3@example.com", "approved"),
            guest("Person 4", "person4@example.com", "pending_approval"),
        ]
        links = chart(rows, luma)["links"]
        into = [link["role"] for link in links if link["target"] == "RSVP’d"]
        out = [role for role, _ in groupby(link["role"] for link in links if link["source"] == "RSVP’d")]
        self.assertEqual(into, ["Volunteers", "Speakers"])
        self.assertEqual(out, into)

    def test_shares_round_half_up(self):
        # 5 / 200 = 2.5% and 1 / 8 = 12.5%: Python's round() would give 2% and 12%.
        self.assertEqual((percent(5, 200), percent(1, 8), percent(1, 3), percent(2, 3)), (3, 13, 33, 67))

    def test_ap_style_as_of(self):
        cases = {
            "2026-11-03T20:20:00Z": "Nov. 3, 2026, 12:20 p.m. PST",
            "2026-09-25T17:05:00+00:00": "Sept. 25, 2026, 10:05 a.m. PDT",
            "2026-03-14T22:00:00Z": "March 14, 2026, 3 p.m. PDT",
            "2026-11-03T20:00:00Z": "Nov. 3, 2026, noon PST",
            # No offset means Los Angeles time.
            "2026-12-01T09:30": "Dec. 1, 2026, 9:30 a.m. PST",
        }
        for timestamp, expected in cases.items():
            with self.subTest(timestamp=timestamp):
                self.assertEqual(format_as_of(parse_as_of(timestamp)), expected)


class PageTest(unittest.TestCase):
    def test_page_loads_nothing_from_the_network(self):
        page = render_page(chart(SHEET, LUMA), "Test Event")
        self.assertIsNone(re.search(r"""(?:\b(?:src|href)\s*=\s*["']?|url\(\s*["']?)\s*https?://""", page, re.IGNORECASE))
        self.assertRegex(page, r'font-family: "et-book";\s*src: url\("data:font/ttf;base64,')

    def test_embedded_data_survives_the_page(self):
        data = chart(SHEET, LUMA)
        data["notes"].append("</script><b>Judges & partners</b>")
        page = render_page(data, "Test Event")
        embedded = re.search(r'<script type="application/json" id="funnel-data">(.*?)</script>', page, re.DOTALL)
        self.assertEqual(json.loads(embedded.group(1)), data)


class CommandTest(unittest.TestCase):
    def test_command_writes_the_page_and_prints_name_matches(self):
        sheet_rows = [*SHEET, person("Person Nine", "person9@example.com", rsvp="TRUE")]  # row 10: no Luma RSVP
        with tempfile.TemporaryDirectory() as directory:
            sheet = Path(directory) / "outreach.csv"
            luma = Path(directory) / "guests.csv"
            output = Path(directory) / "out"
            write_csv(sheet, sheet_rows)
            write_csv(luma, LUMA, encoding="utf-8-sig")
            # No --as-of: the page is as old as its older input.
            older = parse_as_of("2026-11-03T20:00:00Z").timestamp()
            os.utime(luma, (older, older))
            os.utime(sheet, (older + 3600, older + 3600))
            stdout, stderr = io.StringIO(), io.StringIO()
            with redirect_stdout(stdout), redirect_stderr(stderr):
                exit_code = main([
                    "--sheet", str(sheet), "--luma", str(luma), "--event", "Test Event", "--output-dir", str(output),
                ])
            self.assertEqual(exit_code, 0)
            self.assertEqual([path.name for path in output.iterdir()], ["index.html"])
            page = (output / "index.html").read_text(encoding="utf-8")
        self.assertIn("Matched by name, please check:\n  row 4: Person Three (sheet) = Person Q. Three (Luma)", stdout.getvalue())
        self.assertRegex(stderr.getvalue(), r"warning: sheet row 10\b")
        self.assertIn(f"as of {AS_OF}", page)
        self.assertNotIn("prefers-color-scheme", page)
        # Names and emails stay in the terminal.
        for private in ("Person", "Guest Alpha", "example.com"):
            self.assertNotIn(private, page)

    def test_bad_luma_file_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            sheet = Path(directory) / "outreach.csv"
            luma = Path(directory) / "guests.csv"
            output = Path(directory) / "out"
            write_csv(sheet, SHEET)
            write_csv(luma, [["name", "email"], ["Guest 1", "g1@example.com"]])
            stderr = io.StringIO()
            with redirect_stderr(stderr), redirect_stdout(io.StringIO()):
                exit_code = main([
                    "--sheet", str(sheet), "--luma", str(luma), "--event", "Test Event", "--output-dir", str(output),
                ])
            self.assertEqual(exit_code, 1)
            self.assertTrue(stderr.getvalue().startswith("error: "))
            self.assertIn("approval_status", stderr.getvalue())
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
