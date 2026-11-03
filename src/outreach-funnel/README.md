# Outreach funnel

Shows an event's outreach by role as an interactive Sankey chart. People flow from the top row (their role: Volunteers, Speakers, Sponsors, Judges & partners, plus Luma guests we did not invite) to their reply (RSVP’d, Declined, No reply yet) and then to the host's decision on Luma (Accepted, Waiting for host, Host declined). Ribbon width is people; color is role. Ribbons into RSVP’d and Accepted are strong, ribbons into Waiting for host are lighter, and ribbons into Declined, No reply yet and Host declined are faint.

The script writes one web page, `index.html`, to `docs/reports/outreach-funnel/`. The `docs/` folder is not tracked in git, so the page exists only in your local checkout. The page is one self-contained file: it works offline and from a local file and loads nothing from the network.

On the page:

- Hover over a ribbon, or tab to it, to read its people and share. Hover over a bar to list its people by role.
- Click a role (a top-row bar or a row in the role table), or press Enter or Space on it, to pin it: only that role keeps its color. Click it again, press Escape or click empty chart space to clear.
- Click a ribbon, or press Enter or Space on it, to trace it back to its role at the top: only that ribbon and the ribbons of its role that lead to it keep their color. Click it again, press Escape or click empty chart space to clear.
- On a touch screen, a tap acts as hover; a second tap on a role pins it, and a second tap on a ribbon traces it.
- "How we count ⊕" sits in the margin to the right of the chart. Click it, or tab to it and press Space, to show the counting rules; click it again to hide them. On a screen narrower than 1,200 px, it sits above the chart instead.
- Numbered footnotes on the chart point to notes in the same margin, under "How we count": note 1 (after the headline) counts the RSVP matches, and note 2 (after "Invited") counts the people the chart leaves out. The notes stay visible when the rules are hidden. Click a number to jump to its note, which stays yellow for 5 seconds, then fades out over 10 seconds; click the note's number to jump back. Clicking, tapping or pressing a key anywhere else fades it out over 1 second; clicking the same number again restarts it.
- On a screen narrower than 760 px, the chart scrolls sideways.

## Update the chart

1. Export the outreach sheet to a file outside the repository, for example in `/tmp`. Either download it from Google Sheets (File > Download > Comma-separated values) or save the output of `gog sheets get <sheet-id> <range> --json`, run through the ProductTank SF gog gate.
2. Export the Luma guest list (Manage event > Guests > Download as CSV) to a file outside the repository.
3. Run from the repository root:

   ```bash
   ./src/outreach-funnel/src/outreach_funnel.py --sheet /tmp/outreach.json --luma /tmp/luma-guests.csv --event "Nov. 12 After Hours"
   ```

Both exports hold names and emails, so never save them in the repository.

| Option | Meaning |
| --- | --- |
| `--sheet PATH` | Required. The outreach sheet: `.json` is a gog export, anything else is a CSV. Needs the columns `Name`, `Email`, `Label`, `Email Sent`, `Invite Declined`, `Luma RSVP` and `Luma Accept`. |
| `--luma PATH` | Required. The Luma guest CSV export. Needs the columns `name`, `email` and `approval_status`. |
| `--event TEXT` | Required. The page title. |
| `--as-of` | Optional ISO 8601 timestamp. Without it, the chart uses the older of the two files' modification times, because the chart is no newer than its oldest input. Times show in Los Angeles time, AP style: `Nov. 3, 2026, 12:20 p.m. PST`. |
| `--output-dir` | Optional. Writes `index.html` somewhere else. |

The script checks both files before it writes anything. If the sheet or the Luma export breaks a rule below, it prints `error:` and the problem (for the sheet, every problem row by sheet row number and column), writes nothing and exits with status 1. Fix the export and rerun.

After a run, the terminal lists each invitee matched to a Luma guest by name ("Matched by name, please check:") so you can confirm it is the same person. A warning names each sheet row whose `Luma RSVP` or `Luma Accept` checkbox disagrees with Luma. Names stay in the terminal; the page holds counts only.

## How it counts

1. **Invited:** `Email Sent` holds any text except `Bounced`. Bounced emails and people not yet contacted (`Email Sent` blank) are not drawn; margin note 2 counts them. Fully blank rows are skipped.
2. **Role:** the first entry of the `Label` cell (entries are split on `;`). An entry that starts with `Speaker` is Speakers; one that starts with `Volunteer` is Volunteers; any entry with `Sponsor` in it (any case, for example `Sponsor champion` or `Alum/Sponsor`) is Sponsors; `Judge` or `Community Partner` is Judges & partners. An invited row with any other first label, or a blank one, is an error.
3. **Matching:** each invitee is matched to at most one Luma guest. First every invitee is matched by email (trimmed, any case). Then invitees still unmatched are matched by name against the guests still unused: the first and last words of both names must be equal, ignoring case, punctuation and middle names. If two unused guests match one invitee by name, the run stops with an error; add that guest's Luma email to the sheet.
4. **Host decision:** Luma's `approval_status` decides it. `approved` is Accepted, `pending_approval` is Waiting for host and `declined` is Host declined. Any other status is an error.
5. **Reply:** an invitee with a Luma match RSVP’d; Luma is the record. An invitee with no match declined if `Invite Declined` is checked; otherwise there is no reply yet.
6. **Via Luma only:** Luma guests that match no invitee were not invited. They are their own role and are placed by their Luma status in the same way.
7. **Cross-check:** each invitee's `Luma RSVP` checkbox is compared with "has a Luma match" and `Luma Accept` with "Luma status is approved". Margin note 1 says whether they all agree; where they disagree, the chart uses Luma.

Checkbox cells read `TRUE` as checked and blank or `FALSE` as not checked; any other value is an error. These sheet rows are also errors: `Luma Accept` checked without `Luma RSVP`; `Invite Declined` or `Luma RSVP` checked for someone not invited; both `Invite Declined` and `Luma RSVP` checked. A sheet with nobody invited is an error. Shares are whole percents of the exact fraction, with halves rounded up. The page's "How we count" margin note states these rules too.

## Files

- `src/outreach_funnel.py` counts the people and writes the page. The counts go into the page as JSON.
- `assets/outreach-sankey.js` draws the chart from that JSON with d3-sankey and handles hover, focus and pinning. It is plain browser JavaScript with no build step; the script inlines it into the page.
- `assets/d3/` holds d3 7.9.0 (ISC License) and d3-sankey 0.12.3 (BSD 3-Clause License), unchanged, with their license files. Its [README](assets/d3/README.md) lists each file's source and SHA-256.
- `assets/et-book/` holds the ET Book fonts and `assets/tufte.css` holds Tufte CSS, both under the MIT License. The CSS file's header lists its source commit and the two local edits: its font links and its dark mode are removed. The page embeds the fonts as data URIs and stays light.

## Tests

```bash
python3 -m unittest discover -s src/outreach-funnel/tests
```
