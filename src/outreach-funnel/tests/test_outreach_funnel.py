import csv
import io
import json
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from itertools import combinations
from pathlib import Path

from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.outreach_funnel import (
    RENDER_SCALE, WIDTH, Funnel, SheetError, count_funnel, format_as_of, headline, load_fonts, main, parse_as_of,
    plan_layout, read_sheet, stages,
)

HEADER = ["Name", " Email Sent", "Invite Declined", "Luma RSVP ", "Luma Accept", "Notes"]
SUBTITLE = "Nov. 12 After Hours outreach, as of Nov. 3, 2026, 12:20 p.m. PST"


def sample_rows():
    return [
        HEADER,
        ["Person 1", "1", "", "TRUE", "TRUE", ""],
        ["Person 2", "Host text", "", " true ", "FALSE", ""],
        ["Person 3", "1", "TRUE", "", "", ""],
        ["Person 4", "1", "", "", "", ""],
        ["Person 5", " bounced ", "", "", "", ""],
        ["Person 6", "", "", "", "", "follow up"],
        ["", " ", "", "", "", ""],
        ["Person 7", "1", "false", "TRUE", "", ""],
    ]


SAMPLE_FUNNEL = Funnel(listed=7, invited=5, bounced=1, not_invited=1, declined=1, rsvped=3, accepted=1)


def write_csv(path, rows):
    with path.open("w", newline="") as file:
        csv.writer(file).writerows(rows)


def funnel(invited, declined, rsvped, accepted, bounced=0, not_invited=0):
    return Funnel(invited + bounced + not_invited, invited, bounced, not_invited, declined, rsvped, accepted)


class CountTest(unittest.TestCase):
    def test_counts_follow_the_sheet_rules(self):
        counted = count_funnel(sample_rows())
        self.assertEqual(counted, SAMPLE_FUNNEL)
        self.assertEqual((counted.no_reply, counted.waiting), (1, 2))

    def test_inconsistent_rows_are_all_reported(self):
        rows = [
            HEADER,
            ["Person 1", "1", "", "TRUE", "TRUE", ""],
            ["Person 2", "1", "", "", "TRUE", ""],
            ["Person 3", "", "", "TRUE", "", ""],
            ["Person 4", "1", "TRUE", "TRUE", "", ""],
            ["Person 5", "1", "yes", "", "", ""],
        ]
        with self.assertRaises(SheetError) as caught:
            count_funnel(rows)
        message = str(caught.exception)
        for row_number in (3, 4, 5, 6):
            self.assertRegex(message, rf"\brow {row_number}\b")
        self.assertNotRegex(message, r"\brow 2\b")

    def test_missing_columns_are_named(self):
        with self.assertRaises(SheetError) as caught:
            count_funnel([["Name", "Email Sent", "Invite Declined"], ["Person 1", "1", ""]])
        self.assertIn("Luma RSVP", str(caught.exception))
        self.assertIn("Luma Accept", str(caught.exception))

    def test_nobody_invited_is_refused(self):
        with self.assertRaises(SheetError):
            count_funnel([HEADER, ["Person 1", "Bounced", "", "", "", ""], ["Person 2", "", "", "", "", ""]])

    def test_gog_json_and_csv_exports_count_the_same(self):
        with tempfile.TemporaryDirectory() as directory:
            csv_path = Path(directory) / "outreach.csv"
            json_path = Path(directory) / "outreach.json"
            write_csv(csv_path, sample_rows())
            # gog drops trailing blank cells, so most rows are shorter than the header.
            trimmed = [row[: max((i + 1 for i, cell in enumerate(row) if cell), default=0)] for row in sample_rows()]
            json_path.write_text(json.dumps({"range": "Sheet1!A1:F9", "values": trimmed}))
            self.assertLess(len(trimmed[1]), len(HEADER))
            self.assertEqual(count_funnel(read_sheet(csv_path)), SAMPLE_FUNNEL)
            self.assertEqual(count_funnel(read_sheet(json_path)), SAMPLE_FUNNEL)


class WordingTest(unittest.TestCase):
    def test_shares_round_half_up(self):
        shares = {stage.name: stage.share for stage in stages(funnel(invited=200, declined=5, rsvped=8, accepted=1))}
        # 5 / 200 = 2.5% and 1 / 8 = 12.5%: Python's round() would give 2% and 12%.
        self.assertEqual(shares["Declined"], "3% of invited")
        self.assertEqual(shares["RSVP’d"], "4% of invited")
        self.assertEqual(shares["Accepted"], "13% of RSVPs")
        self.assertEqual(shares["Invited"], "")

    def test_headline_grammar(self):
        self.assertEqual(headline(funnel(83, 5, 12, 8)), "12 of 83 invitees RSVP’d; 8 are accepted.")
        self.assertEqual(headline(funnel(1, 0, 1, 1)), "1 of 1 invitee RSVP’d; 1 is accepted.")
        self.assertEqual(headline(funnel(83, 5, 0, 0)), "None of 83 invitees has RSVP’d yet.")

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


class LayoutTest(unittest.TestCase):
    def test_layout_fits_for_large_counts(self):
        big = funnel(invited=8_765, declined=1_234, rsvped=5_678, accepted=4_321, bounced=1_234, not_invited=2_346)
        layout = plan_layout(big, SUBTITLE, load_fonts())
        self.assertIn("8,765", [text.text for text in layout.texts])
        draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        boxes = [draw.textbbox(text.xy, text.text, font=text.font, anchor=text.anchor) for text in layout.texts]
        width, height = WIDTH * RENDER_SCALE, layout.height * RENDER_SCALE
        for text, (left, top, right, bottom) in zip(layout.texts, boxes):
            with self.subTest(text=text.text):
                self.assertTrue(0 <= left and 0 <= top and right <= width and bottom <= height)
        for first, second in combinations(boxes, 2):
            overlap = first[0] < second[2] and second[0] < first[2] and first[1] < second[3] and second[1] < first[3]
            self.assertFalse(overlap, (first, second))

    def test_text_that_cannot_fit_is_refused(self):
        with self.assertRaisesRegex(ValueError, "canvas edge"):
            plan_layout(SAMPLE_FUNNEL, "A very long event name " * 6, load_fonts())


class CommandTest(unittest.TestCase):
    def test_command_writes_page_gif_and_png(self):
        with tempfile.TemporaryDirectory() as directory:
            sheet = Path(directory) / "outreach.csv"
            output = Path(directory) / "out"
            write_csv(sheet, sample_rows())
            with redirect_stdout(io.StringIO()):
                exit_code = main([
                    "--sheet", str(sheet), "--event", "Test Event", "--as-of", "2026-11-03T20:20:00Z",
                    "--output-dir", str(output),
                ])
            self.assertEqual(exit_code, 0)
            self.assertEqual(sorted(path.name for path in output.iterdir()), ["index.html", "outreach-funnel.gif", "outreach-funnel.png"])
            with Image.open(output / "outreach-funnel.gif") as animation:
                self.assertGreater(animation.n_frames, 1)
                self.assertNotIn("loop", animation.info)
                gif_size = animation.size
            with Image.open(output / "outreach-funnel.png") as still:
                self.assertEqual(still.size, gif_size)
            page = (output / "index.html").read_text()
        self.assertNotIn("prefers-color-scheme", page)
        self.assertNotIn("<script", page)
        self.assertIsNone(re.search(r"https?://", page))
        self.assertRegex(page, r'font-family: "et-book";\s*src: url\("data:font/ttf;base64,')
        for count in ("5 invited", "1 declined", "3 RSVP’d", "1 accepted"):
            self.assertIn(count, page)
        self.assertNotIn("Person", page)

    def test_bad_sheet_writes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            sheet = Path(directory) / "outreach.csv"
            output = Path(directory) / "out"
            write_csv(sheet, [HEADER, ["Person 1", "", "", "TRUE", "", ""]])
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                exit_code = main(["--sheet", str(sheet), "--event", "Test Event", "--output-dir", str(output)])
            self.assertEqual(exit_code, 1)
            self.assertTrue(stderr.getvalue().startswith("error: "))
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
