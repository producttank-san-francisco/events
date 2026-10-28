# RSVP attendance: three visual options

## Recommendation

**Option A was selected: the three-stage slopegraph.** Its compact layout follows each month’s counts with less clutter and labels clear of the lines.

Option A is now **720 × 540**, 40% narrower than the original 1200-pixel image, and is animated like the existing slopegraph GIF. B and C remain static 1200 × 1040 comparison images. A leads with its takeaway (“October is on pace for ≈53 attendees”) and a small grey “as of Oct. 28, 2026” at the upper right, names the stages (RSVPs, Email, Attended) in grey on one shared row along the bottom, joins each name to its column’s dots with a faint dashed guide, shows whole-number percentages and ends with two smaller plain-language notes. The brand, study badge, top header row, repeated formulas, axis ticks and long footer were removed from A; exact arithmetic, the full snapshot time and caveats remain below. All options reuse the existing palette and font loader, with direct labels and no legend or gridlines.

## Counts and snapshot

Input: the committed [aggregate counts](../rsvp-slopegraph/stats.json), also shown in the [existing slopegraph report](../rsvp-slopegraph/report.md).

| Stage | September 30, Cribl | October 28, Vapi |
| --- | ---: | ---: |
| Named guests | 225 | 140 |
| Unnamed Meetup plus-ones | 12 | 12 |
| RSVPs: named + plus-ones | 237 | 152 |
| Guests with email | 136 | 86 |
| Attendance | 84, door head count | Unknown; estimated below |

The October input is the Vapi guest list as of its automatic refresh at **October 28, 2026, 15:00:09 UTC / 8:00:09 a.m. PDT**, confirmed unchanged by a live read of the sheet at 9:01 a.m. PDT. Named guests are the 140 rows still marked registered; 4 rows marked “No longer registered” are excluded. Guests with email are the registered rows with an email address. The 12 unnamed plus-ones are Meetup “Yes” RSVP companions from the same refresh’s Meetup export; they have no rows in the sheet.

## Exact arithmetic

Fractions below are exact. Decimals with an ellipsis continue; headline percentages and count labels are rounded only for reading. Estimates are calculated with the unrounded fractions.

| Quantity | Exact calculation | Decimal for reading |
| --- | --- | --- |
| September email share | 136/237 | 57.383966244725738…% |
| October email share | 86/152 = 43/76 | 56.578947368421052…% |
| September drop, RSVPs → with email | 101/237 | 42.616033755274261…% |
| October drop, RSVPs → with email | 66/152 = 33/76 | 43.421052631578947…% |
| Email-share gap, September minus October | 100 × (136/237 − 43/76) = 3625/4503 | 0.805018876304685… percentage points |
| September attendees per guest with email | 84/136 = 21/34 | 61.764705882352941…% |
| Email-based estimate (current main) | 86 × 21/34 = 903/17 | 53.117647058823529… → about **53** |
| RSVP-based estimate (earlier PR #7 draft, 2be0520) | 152 × 84/237 = 4256/79 | 53.873417721518987… → about **54** |
| RSVP-based estimate minus email-based estimate | 4256/79 − 903/17 = 1015/1343 | 0.755770662695457… people |

**“About the same percentage drop” is fair; “the same percentage drop” is not.** October retains a smaller email share by exactly 3625/4503 percentage points. B and C show 57.4% and 56.6%; A’s whole-number labels both round to 57%, so the exact gap appears only in B, C and the table above.

### Why 53 and 54 differ

- **53** scales attendance with the email-guest count: October has 86/136 as many email guests as September.
- **54** scales attendance with all RSVPs: October has 152/237 as many RSVPs as September.
- Since October’s email share is slightly lower, the email-based method yields the lower estimate. They would agree if the email shares were identical.
- **PR #7 history:** an [earlier draft, `2be0520`](https://github.com/producttank-san-francisco/events/blob/2be052039587a2ab31c8cf2c3eb689effe548d6d/src/rsvp-slopegraph/src/rsvp_slopegraph.py), used the RSVP-based calculation, which gave **about 51** on the Oct. 27 snapshot (`144 × 84/237`). PR #7’s [merged head, `dc44c7f`](https://github.com/producttank-san-francisco/events/blob/dc44c7f/src/rsvp-slopegraph/src/rsvp_slopegraph.py), switched to the email-based calculation, which gave **about 49** on that snapshot (`80 × 84/136`). Current main uses that email-based estimate, as described in the [renderer instructions](../../../src/rsvp-slopegraph/README.md#update-the-numbers). This report keeps both formulas to explain the difference.

## Assumptions and limits

1. **84/136 is a ratio, not a measured conversion rate.** The 84 attendees are a door head count and may include people without email. We have not identified a cohort of 136 email guests and verified which 84 attended. An arrow between these aggregate counts must not imply that evidence exists.
2. **October repeats September’s aggregate attendance-to-email ratio by assumption.** Similar email shares do not establish similar attendance. Different venues, event content, registration timing or attendee mix could change the result. No uncertainty interval is supported by these counts alone; 53.1 is arithmetic precision, not predictive certainty.
3. **RSVPs include unnamed companions.** The plus-ones are outside the named rows. Missing email does not mean a person was rejected or did not attend.
4. **This is a running October snapshot against a completed September event.** It is not a final October registration count.

## Option A — log-scale three-stage slopegraph

![Option A animation: September and October lines draw left to right across RSVPs, Email and Attended; each step’s count and percentage fade in as the line arrives, and the chart holds on the final frame.](option-a-log-scale-three-stage-slopegraph.gif)

The [final frame as a still PNG](option-a-log-scale-three-stage-slopegraph.png) is also written for documents that cannot show GIFs.

**What a viewer gets in five seconds:** both months lose a similar proportion between RSVPs and email guests; extending October with September’s next ratio gives about 53 attendees. Counts remain visible throughout.

**Organizing principle:** follow each month left to right. Equally spaced stages and one shared logarithmic count mapping make equal proportional changes parallel; no points are nudged away from their values.

**Honesty risks:** a log scale is unfamiliar and has no zero. Equal visual distances mean equal multipliers, not equal numbers of people. The chart says this plainly (“same slope = same share kept”) instead of naming the scale, and labels every count directly; it does not need a count axis. The first steps are nearly, not exactly, parallel. Both whole-percent labels read 57%, which hides that small difference; its exact size is in the arithmetic table above. A three-stage line can suggest a tracked group, so the chart says we don’t know which of the 84 attendees had email, making 62% a rough guide. Dashed October attendance, its hollow endpoint and the orange “assumed” under ≈53 mark the assumption. The endpoint is plotted at the unrounded 903/17 and labeled approximately 53.

**Animation:** built with the existing GIF’s exact timing: 25 fps, a 0.4-second opening pause, 90 eased steps with October starting slightly after September, an 0.08-of-the-reveal fade for each label, then a 2.84-second hold on the last frame. Total 6.92 seconds, played once, matching the existing slopegraph GIF. Left labels, stage names, title, date and notes stay visible throughout. Each line’s middle count and first percentage fade in when it reaches the Email column; its end count, second percentage and “assumed” fade in when it reaches Attended. Labels never move, so every frame keeps the same clearance as the still.

## Option B — two step-ratio panels

![Option B: two equal-width panels on identical 0–100% scales compare September and October email shares, then show September’s attendance-to-email ratio repeated as an explicit October assumption.](option-b-step-ratio-small-multiples.png)

**What a viewer gets in five seconds:** 57.4% and 56.6% are close, not identical; 61.8% is then assumed for October, producing about 53. The measured comparison and borrowed assumption occupy separate panels.

**Organizing principle:** compare ratios rather than infer them from line angles. Both panels have the same pixel width and the same complete 0–100% scale. Rows and dots have direct month, count and percentage labels. The hollow October dot says “assumed.”

**Honesty risks:** the 0.8050…-point difference is visually small on a full scale; the exact fractions and gap are printed below the panel rather than amplified with a cropped axis. Two aligned 61.8% dots could imply independent confirmation, so the October label and subtitle explicitly say otherwise. The second panel’s heading is not evidence of cohort tracking; the aggregate-ratio caveat remains visible. Absolute event sizes are less immediate than in A or C, though the numerator/denominator labels retain them.

**Effort to animate like the existing GIF:** medium. Keep axes and labels in place, reveal the measured left-panel dots, reveal September’s right-panel dot, then introduce October’s hollow assumed dot and the formula. It needs dot-reveal choreography rather than reusing the existing slopegraph motion unchanged. Do not present the assumed dot as a second observation, or animate a percentage label independently from its numerator and denominator. No animation has been implemented.

## Option C — counts-and-ratios table-graphic

![Option C: a stage-by-month table with direct counts, proportional zero-based inline bars, two ratio rows, and an explicitly assumed October attendance cell.](option-c-counts-and-ratios-table-graphic.png)

**What a viewer gets in five seconds:** all source counts and the estimated cell are easy to locate; the two ratio rows explain the comparison without decoding a graph.

**Organizing principle:** scan stage rows and month columns. Inline bars have identical 0–250-person mappings and visible zero starts. The estimate cell is marked “ASSUMED,” uses an approximate number, and has a dashed bar. Ratio rows use the same month columns as the counts.

**Honesty risks:** the inline bars show absolute counts, not percentage changes; the viewer must read the ratio rows to see the argument. There is no log-scale trick, but it is denser and less sequential than B. A precise decimal in a table can look more certain than the prediction warrants; the approximation sign, assumption label and footer distinguish calculation from observation.

**Effort to animate like the existing GIF:** low to medium. The table layout is static; reveal the observed rows first, then the ratio rows and estimated cell. The current palette, font and GIF encoding can be reused, but row and bar reveals need new drawing logic. Keep count labels stable rather than counting through invented intermediate observations. No animation has been implemented.

## Reproduce and verification

Requires Python 3, Pillow and Gifski, as well as this repository’s existing renderer modules. From the repository root:

```sh
python3 -B docs/reports/rsvp-attendance-funnel-visual-options/render_options.py
```

The [render script](render_options.py) reads the saved stats, imports the existing palette, font loader and animation timing, uses exact rational arithmetic until drawing, and writes only the three PNGs and Option A’s GIF beside itself. It does not update the source report, stats, GIF or Google Sheet. Layout and copy are mockups for this snapshot, not a hardened general-purpose chart API.

Verification performed: ran the renderer and opened a contact sheet of eight A animation frames, from the opening pause to the final hold. A rendered at 720 × 540; all 18 text labels passed the render-time check for at least six pixels of clearance from all four full line segments and all three dashed guides, with no text overlaps. Text bounds also passed the canvas-edge check on every frame. The final GIF frame matches the still PNG within GIF color quantization. Read back from the files, the A GIF and the existing slopegraph GIF both total 6.92 seconds, open with a 400 ms frame, end with a 2,840 ms hold and have no loop flag. B and C still rendered at 1200 × 1040. After the Oct. 28 data refresh, all four images were re-rendered, the label and canvas checks passed again, and the slopegraph unit tests passed (9 of 9). No device-specific display check is claimed.

## Selected design

**Option A was selected** because following each month’s count path makes the similar proportional drops and the assumed October extension easy to compare. The narrow layout leads with the takeaway; stable direct labels, shared stage guides and plain-language caveats keep the chart compact without hiding counts or uncertainty. Animation reveals each step and its labels together, then holds on the final still. B and C remain as the alternatives considered, not open choices. Both attendance formulas and the complete snapshot caveats remain in this report rather than on the compact chart.
