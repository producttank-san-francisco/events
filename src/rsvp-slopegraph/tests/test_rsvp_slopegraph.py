import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.rsvp_slopegraph import (
    RENDER_SCALE, build_stats, load_fonts, load_stats, plan_layout, right_name, right_value, segment_hits_box,
    spread_labels,
)


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

    def test_real_font_labels_do_not_overlap(self):
        fonts = load_fonts()
        draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        layout = plan_layout(build_stats(sample_data()), fonts, draw)
        for left in (True, False):
            boxes = []
            for item in layout.placed:
                y = item.left_label_y if left else item.right_label_y
                value = str(item.stat.september) if left else right_value(item.stat)
                name = item.stat.name if left else right_name(item.stat)
                value_box = draw.textbbox((0, y), value, font=fonts.label, anchor="lm")
                name_box = draw.textbbox((0, y), name, font=fonts.axis, anchor="lm")
                boxes.append((min(value_box[1], name_box[1]), max(value_box[3], name_box[3])))
            boxes.sort()
            for above, below in zip(boxes, boxes[1:]):
                self.assertLessEqual(above[1], below[0])

    def test_change_labels_clear_every_line(self):
        draw = ImageDraw.Draw(Image.new("RGB", (1, 1)))
        layout = plan_layout(build_stats(sample_data()), load_fonts(), draw)
        self.assertEqual([label.text for label in layout.changes], ["−39%", "−41%"])
        segments = [((layout.x_left, item.left_y), (layout.x_right, item.right_y)) for item in layout.placed]
        for label in layout.changes:
            left, top, right, bottom = draw.textbbox((label.x, label.y), label.text, font=layout.change_font, anchor="mm")
            # Lines are 3 px wide, so the drawn stroke must stay outside the box grown by half its width.
            pad = 1.5 * RENDER_SCALE
            box = (left - pad, top - pad, right + pad, bottom + pad)
            for start, end in segments:
                self.assertFalse(segment_hits_box(start, end, box), label.text)


class StatsTest(unittest.TestCase):
    def test_rsvps_add_plus_ones_and_attendance_scales_by_email_guests(self):
        stats = {stat.name: stat for stat in build_stats(sample_data())}
        self.assertEqual((stats["RSVPs"].september, stats["RSVPs"].october), (237, 144))
        # 80 email guests × (84 attended / 136 email guests) = 49.4.
        self.assertEqual(stats["Attended"].october, 49)
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

    def test_invalid_counts_name_the_event_and_field(self):
        fields = {
            "september": ("named_guests", "guests_with_email", "unnamed_plus_ones", "attended"),
            "october": ("named_guests", "guests_with_email", "unnamed_plus_ones"),
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "stats.json"
            for event, keys in fields.items():
                for key in keys:
                    for value in ("132", None, True, -1, 1.5):
                        with self.subTest(event=event, key=key, value=value):
                            data = sample_data()
                            data[event][key] = value
                            path.write_text(json.dumps(data))
                            with self.assertRaisesRegex(ValueError, f"{event}.{key} must be a non-negative whole number"):
                                load_stats(path)


if __name__ == "__main__":
    unittest.main()
