import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.rsvp_slopegraph import build_stats, load_stats, spread_labels


def sample_data():
    return {
        "september": {
            "label": "Sept. 30", "venue": "Cribl", "named_guests": 225,
            "guests_with_email": 136, "unnamed_plus_ones": 12, "attended": 84,
        },
        "october": {
            "label": "Oct. 28", "venue": "Vapi", "as_of": "2026-10-27T17:50:13Z",
            "named_guests": 132, "guests_with_email": 80, "unnamed_plus_ones": 12,
        },
    }


class SpreadLabelsTest(unittest.TestCase):
    def test_labels_with_room_stay_at_their_lines(self):
        self.assertEqual(spread_labels([100, 200, 300], 20, 0, 400), [100, 200, 300])

    def test_crowded_labels_separate_around_their_mean(self):
        placed = spread_labels([100, 108, 300], 20, 0, 400)
        self.assertEqual(placed[1] - placed[0], 20)
        self.assertEqual((placed[0] + placed[1]) / 2, 104)
        self.assertEqual(placed[2], 300)

    def test_crowding_at_top_edge_moves_only_the_crowded_group(self):
        placed = spread_labels([0, 5, 200], 20, 0, 400)
        self.assertEqual(placed, [0, 20, 200])

    def test_chain_reaction_keeps_every_gap(self):
        placed = sorted(spread_labels([100, 110, 120, 130], 20, 0, 400))
        self.assertEqual([b - a for a, b in zip(placed, placed[1:])], [20, 20, 20])


class StatsTest(unittest.TestCase):
    def test_rsvps_add_plus_ones_and_attendance_uses_september_turnout(self):
        stats = {stat.name: stat for stat in build_stats(sample_data())}
        self.assertEqual((stats["RSVPs"].september, stats["RSVPs"].october), (237, 144))
        # 84 / 237 rounds to 35%; 144 x 0.35 = 50.4.
        self.assertEqual(stats["Attended"].october, 50)
        self.assertTrue(stats["Attended"].estimate)
        self.assertFalse(stats["RSVPs"].estimate)

    def test_missing_field_names_the_event_and_field(self):
        data = sample_data()
        del data["october"]["as_of"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.json"
            path.write_text(json.dumps(data))
            with self.assertRaisesRegex(ValueError, "october is missing as_of"):
                load_stats(path)


if __name__ == "__main__":
    unittest.main()
