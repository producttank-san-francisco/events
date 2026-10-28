# RSVP slopegraph

Compares the September and October events on four stats: RSVPs, named guests, guests with email and attendance. The script writes a report and animated slopegraph to `docs/reports/rsvp-slopegraph/`. The `docs/` folder is not tracked in git, so these files exist only in your local checkout.

The GIF reuses the [GitHub traffic animation](../github-traffic/README.md)'s colors, fonts, frame rate and Gifski encoding. It needs the same setup: `brew install gifski` and `python3 -m pip install Pillow`.

## Update the numbers

All numbers live in `docs/reports/rsvp-slopegraph/stats.json`, which is local only. The file holds aggregate counts only; never add guest names or emails.

1. Update the October values (`named_guests`, `guests_with_email`, `unnamed_plus_ones`) and set `as_of` to the guest list's timestamp in UTC.
2. Run from the repository root:

   ```bash
   ./src/rsvp-slopegraph/src/rsvp_slopegraph.py
   ```

The script rewrites `slopegraph.gif` and `report.md`. It computes RSVPs as named guests plus unnamed Meetup plus-ones. It estimates October attendance by scaling September's attendance by the change in guests with email, using the unrounded ratio, then rounds the head count: `80 × (84 / 136) ≈ 49`. Only the displayed email-guest turnout percentage is rounded to a whole percent. The headline marks October RSVPs as a running count with “so far”. Count fields must be non-negative whole numbers.

The GIF plays once and holds its final frame. Smaller, faded percentage labels show the RSVP and email-guest changes from September: `(October − September) / September × 100`. Each label sits above its line and moves outward until it clears every line. Line slopes show absolute head-count changes, not percentage changes.

## Tests

```bash
python3 -m unittest discover -s src/rsvp-slopegraph/tests
```
