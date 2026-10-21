import copy
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from PIL import Image

from src.github_traffic_report import ReportError, main, render_report, run_gh_api, validate_snapshot
from src.traffic_animation.github_traffic_animation import nice_axis_max, render_traffic_gif, series_from_snapshot


def sample_snapshot():
    return {
        "schema_version": 1,
        "repository": "example/events",
        "fetched_at": "2026-10-06T12:00:00Z",
        "source": "GitHub REST API repository traffic endpoints",
        "report": {
            "focus_path": "/example/events/tree/main/event/jorge",
            "focus_label": "Jorge’s page",
        },
        "views": {
            "count": 10,
            "uniques": 6,
            "views": [
                {"timestamp": "2026-10-04T00:00:00Z", "count": 4, "uniques": 3},
                {"timestamp": "2026-10-05T00:00:00Z", "count": 6, "uniques": 4},
            ],
        },
        "clones": {
            "count": 3,
            "uniques": 2,
            "clones": [
                {"timestamp": "2026-10-04T00:00:00Z", "count": 1, "uniques": 1},
                {"timestamp": "2026-10-05T00:00:00Z", "count": 2, "uniques": 1},
            ],
        },
        "referrers": [{"referrer": "github.com", "count": 2, "uniques": 2}],
        "paths": [
            {"path": "/example/events", "title": "Overview", "count": 5, "uniques": 4},
            {
                "path": "/example/events/tree/main/event/jorge",
                "title": "Jorge",
                "count": 3,
                "uniques": 2,
            },
        ],
    }


class ValidationTests(unittest.TestCase):
    def test_rejects_total_that_does_not_match_daily_rows(self):
        snapshot = sample_snapshot()
        snapshot["views"]["count"] = 11

        with self.assertRaisesRegex(ReportError, "daily rows total 10"):
            validate_snapshot(snapshot)

    def test_rejects_unique_count_above_total(self):
        snapshot = sample_snapshot()
        snapshot["paths"][0]["uniques"] = 6

        with self.assertRaisesRegex(ReportError, "uniques exceeds"):
            validate_snapshot(snapshot)


class RenderingTests(unittest.TestCase):
    def test_render_is_deterministic_and_explains_limits(self):
        snapshot = sample_snapshot()

        first = render_report(snapshot)
        second = render_report(copy.deepcopy(snapshot))

        self.assertEqual(first, second)
        self.assertIn("GitHub counted 6 unique visitors and 10 page views", first)
        self.assertIn("**2 unique visitors** opened the page **3 times**", first)
        self.assertIn("**This does not show link clicks.**", first)
        self.assertIn("Daily unique counts cannot be added", first)


class AnimationTests(unittest.TestCase):
    def test_animation_uses_cumulative_at_a_glance_data(self):
        snapshot = sample_snapshot()

        dates, views, clones = series_from_snapshot(snapshot)
        first = render_traffic_gif(snapshot)
        second = render_traffic_gif(copy.deepcopy(snapshot))

        self.assertEqual(len(dates), 2)
        self.assertEqual(views, [4, 10])
        self.assertEqual(clones, [1, 3])
        self.assertEqual(first, second)
        with Image.open(io.BytesIO(first)) as animation:
            self.assertEqual(animation.size, (720, 720))
            self.assertTrue(animation.is_animated)

    def test_animation_has_steady_motion_and_separate_holds(self):
        with Image.open(io.BytesIO(render_traffic_gif(sample_snapshot()))) as animation:
            durations = []
            for index in range(animation.n_frames):
                animation.seek(index)
                durations.append(animation.info["duration"])

        self.assertEqual(durations[0], 360)
        # Temporal dithering can split the final hold before the pixels settle.
        self.assertGreaterEqual(durations[-1], 1000)
        self.assertEqual(set(durations[1:-1]), {40})
        self.assertEqual(sum(durations), 6240)

    def test_animation_trims_empty_leading_days_without_changing_totals(self):
        snapshot = sample_snapshot()
        snapshot["views"]["views"].insert(
            0,
            {"timestamp": "2026-10-03T00:00:00Z", "count": 0, "uniques": 0},
        )
        snapshot["clones"]["clones"].insert(
            0,
            {"timestamp": "2026-10-03T00:00:00Z", "count": 0, "uniques": 0},
        )

        dates, views, clones = series_from_snapshot(snapshot)

        self.assertEqual(dates[0], "2026-10-04T00:00:00Z")
        self.assertEqual(views[-1], 10)
        self.assertEqual(clones[-1], 3)
        self.assertEqual(nice_axis_max(316), 400)


class ApiTests(unittest.TestCase):
    def test_failed_api_call_is_logged_and_fails_loudly(self):
        calls = []

        def failed_runner(*_args, **_kwargs):
            return subprocess.CompletedProcess([], 1, stdout="", stderr="HTTP 403: Resource not accessible")

        with self.assertRaisesRegex(ReportError, "HTTP 403"):
            run_gh_api("example/events", "traffic/views", calls, runner=failed_runner)

        self.assertEqual(calls[0]["status"], "error")
        self.assertEqual(calls[0]["exit_code"], 1)

    def test_invalid_json_is_logged_and_fails_loudly(self):
        calls = []

        def invalid_runner(*_args, **_kwargs):
            return subprocess.CompletedProcess([], 0, stdout="not json", stderr="")

        with self.assertRaisesRegex(ReportError, "invalid JSON"):
            run_gh_api("example/events", "traffic/views", calls, runner=invalid_runner)

        self.assertEqual(calls[0]["status"], "invalid_json")


class CommandTests(unittest.TestCase):
    def test_missing_encoder_fails_without_writing_partial_outputs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "input.json"
            output = root / "output"
            source.write_text(json.dumps(sample_snapshot()), encoding="utf-8")
            stderr = io.StringIO()

            with patch.dict(os.environ, {"PATH": ""}), redirect_stderr(stderr):
                exit_code = main(["--from-snapshot", str(source), "--output-dir", str(output)])

            self.assertEqual(exit_code, 1)
            self.assertIn("install Gifski", stderr.getvalue())
            invocation = json.loads((output / "invocations.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(invocation["status"], "error")
            self.assertEqual({path.name for path in output.iterdir()}, {"invocations.jsonl"})

    def test_saved_snapshot_renders_report_and_invocation_log(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source = root / "input.json"
            output = root / "output"
            source.write_text(json.dumps(sample_snapshot()), encoding="utf-8")

            exit_code = main(["--from-snapshot", str(source), "--output-dir", str(output)])

            self.assertEqual(exit_code, 0)
            self.assertEqual((output / "report.md").read_text(encoding="utf-8"), render_report(sample_snapshot()))
            invocation = json.loads((output / "invocations.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(invocation["status"], "success")
            self.assertEqual(invocation["api_calls"], [])

if __name__ == "__main__":
    unittest.main()
