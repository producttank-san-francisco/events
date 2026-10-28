# GitHub traffic

## Traffic reports

Repository administrators can create a shareable 14-day GitHub traffic report:

```bash
./src/github-traffic/src/github_traffic_report.py --help
```

The help lists the required repository, focus-page, and output options. Output goes to `docs/reports/github-traffic/` by default: the report, animated chart, source data and invocation log. The `docs/` folder is not tracked in git, so these files exist only in your local checkout.

The command requires an authenticated [GitHub CLI](https://cli.github.com/) account with repository administration access, [Pillow](https://pillow.readthedocs.io/), and the [Gifski CLI](https://gif.ski/). It writes the report, animation, exact API source data, and an invocation log. GitHub traffic shows page views and Git clones; it does not show clicks on outbound links.

The GIF renderer is in `src/github-traffic/src/traffic_animation/`.

### GIF quality and setup

The GIF is 720×720 pixels. Each frame is drawn at 2160×2160, then reduced with Lanczos resampling for smooth lines and text. The line reveal has 25 frames per second, gentle easing, a 360-millisecond opening hold, and a 1.6-second final hold. Gifski encodes at maximum color and motion quality. PNG frames are temporary and are removed after encoding.

Gifski can split a stationary hold across several GIF frames while temporal dithering settles. The reveal uses 108 motion steps instead of 72: one-third slower at the same 25-frame-per-second cadence. The loop lasts 6.24 seconds, with unchanged opening and final holds. The opening hold is 360 milliseconds rather than the earlier 350 milliseconds so all input timings are exact multiples of the 40-millisecond frame interval.

On macOS:

```bash
brew install gifski
python3 -m pip install Pillow
```

To fetch current traffic and regenerate the report and GIF, run from the repository root:

```bash
./src/github-traffic/src/github_traffic_report.py \
  --repo producttank-san-francisco/events \
  --focus-path /producttank-san-francisco/events/tree/main/2026-09-30-ai-workflows-pms-use-every-day/jorge-alcantara \
  --focus-label 'Jorge’s page'
```

Use this live refresh when the traffic data changes. The saved-snapshot command below does not check GitHub for newer activity, and the GIF does not update automatically.

To rebuild from saved GitHub data in your local checkout without API access, run from the repository root:

```bash
./src/github-traffic/src/github_traffic_report.py --from-snapshot docs/reports/github-traffic/source.json
```

Other platforms can install the Gifski CLI from its [releases](https://github.com/ImageOptim/gifski/releases). It must be on `PATH`. Encoder errors fail the command and are recorded in the invocation log; there is no lower-quality fallback. Gifski is an AGPL-licensed external executable, not a vendored or linked library.

## Tests

Run the focused test suite from the repository root:

```bash
python3 -m unittest discover -s src/github-traffic/tests
```

### Delivery verification

- All 10 tests passed, including motion cadence and missing-encoder failure.
- On Oct. 12, 2026, the live command fetched all four traffic endpoints and regenerated the report, snapshot, GIF, and invocation log. The latest daily data runs through Oct. 11, UTC.
- Replay produced byte-identical source JSON, Markdown, and GIF bytes on this workstation with Gifski 1.34.0.
- The refreshed data changed the totals from 316 to 327 page views and from 116 to 124 clones.
- The GIF loaded in Chromium at its native 720×720 size; playback screenshots were captured at two points in the loop. The preview tab was closed.
- Decoded first, middle, and final frames were inspected at native size. Labels were readable and unclipped, with final totals of 327 page views and 124 clones.
- The GIF is 720×720 pixels, 639,815 bytes, with 113 encoded frames, a 6.24-second infinite loop, and 40-millisecond motion frames. The input reveal uses 108 steps rather than 72, so its speed is reduced by one-third without lowering the frame rate.
- Initial implementation checks also covered a single-day snapshot and encoder failure. Failure returned a clear error and wrote only an error log, not partial report files.
- Three initial simplification reviews found no blocking issues. Applied: simpler easing calculation and lower compression for temporary, lossless PNG files. Deferred: static-layer caching, because it adds structure without a measured need.
- No lint or type-check command is configured. Cross-platform byte identity is not guaranteed because fonts and encoder versions can differ.

GIF SHA-256: `1d1c1fb0de3c1608c7bb994bc232db90825bf0391d75b2fb23e9ff1eb9532815`.
