# Outreach funnel

Shows an event's outreach in four stages: how many people we invited, how many declined, how many RSVP’d on the Luma event page and how many of those the hosts accepted. The script writes an animated GIF, a PNG of its final frame and a web page, `index.html`, to `docs/reports/outreach-funnel/`. The `docs/` folder is not tracked in git, so these files exist only in your local checkout.

The chart follows [Tufte CSS](https://edwardtufte.github.io/tufte-css/): ET Book type, warm off-white paper, direct labels and no axes. Every bar uses one scale from zero. The faint bar behind each stage is the group it is counted from. The GIF reuses the [GitHub traffic animation](../github-traffic/README.md)'s Gifski encoder and the [RSVP slopegraph](../rsvp-slopegraph/README.md)'s reveal timing. It needs the same setup: `brew install gifski` and `python3 -m pip install Pillow`.

## Update the chart

1. Export the outreach sheet to a file outside the repository, for example in `/tmp`. Either download it from Google Sheets (File > Download > Comma-separated values) or save the output of `gog sheets get <sheet-id> <range> --json`, run through the ProductTank SF gog gate. The export holds names and emails, so never save it in the repository.
2. Run from the repository root:

   ```bash
   ./src/outreach-funnel/src/outreach_funnel.py --sheet /tmp/outreach.json --event "Nov. 12 After Hours"
   ```

The script picks the parser by file name: `.json` is a gog export, anything else is a CSV. `--as-of` takes an ISO 8601 timestamp; without it, the chart uses the export file's modification time. Times show in Los Angeles time, AP style: `Nov. 3, 2026, 12:20 p.m. PST`. `--output-dir` writes somewhere else.

The script checks the whole sheet before it draws anything. If any row breaks the rules below, it lists every problem row by sheet row number and column, writes no files and exits with status 1. Fix the sheet, export again and rerun.

## How it counts

Each row with any text is one person on the list; fully blank rows are skipped. Checkbox cells read `TRUE` as checked and blank or `FALSE` as not checked. Any other checkbox value is an error.

| Stage | Rule |
| --- | --- |
| Invited | `Email Sent` holds any text except `Bounced`: emailed or texted. |
| Declined | Invited, and `Invite Declined` is checked. |
| RSVP’d | Invited, and `Luma RSVP` is checked: registered on the Luma event page. |
| Accepted | RSVP’d, and `Luma Accept` is checked: a host approved the registration. |
| Not counted | `Email Sent` is `Bounced` (bounced email) or blank (not yet contacted). |

These rows are errors: `Luma Accept` checked without `Luma RSVP`; `Invite Declined` or `Luma RSVP` checked for someone not invited; both `Invite Declined` and `Luma RSVP` checked. A sheet with nobody invited is also an error. Shares are whole percents of the exact fraction, with halves rounded up.

The output holds aggregate counts only. No names, emails or sheet rows are written anywhere.

## Fonts and styles

`assets/et-book/` holds the ET Book fonts and `assets/tufte.css` holds Tufte CSS, both under the MIT License. The CSS file's header lists its source commit and the two local edits: its font links and its dark mode are removed. The page inlines the CSS and embeds the fonts as data URIs, so it works offline and from a local file, makes no outside requests and stays light.

## Tests

```bash
python3 -m unittest discover -s src/outreach-funnel/tests
```
