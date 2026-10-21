# GitHub traffic report hardening plan

## Goal

Create one command that fetches GitHub repository traffic, saves the source data, and writes a shareable report that a non-technical reader can scan in 15 seconds.

## Success criteria

- Pull repository views, clones, referring sites, and popular pages through the authenticated GitHub API.
- Fail with a clear error when authentication, API access, or response validation fails.
- Save the unmodified API responses with the report so every number can be checked.
- Log each run’s arguments, API outcomes, elapsed time, and generated-file hashes without logging credentials.
- Explain what each metric means and what it cannot prove, especially that page views do not measure outbound link clicks.
- Produce identical Markdown for identical saved source data.
- Cover valid rendering, malformed responses, and API errors with focused automated tests.

## Implementation

1. Add a Python standard-library CLI under `src/github-traffic/src/` that calls `gh api` for the four traffic endpoints.
2. Validate the repository name and every response before writing output.
3. Write source JSON and Markdown atomically, then append a machine-readable invocation record.
4. Support rendering from saved source JSON so formatting is testable without network access.
5. Generate the current ProductTank report, focused on Jorge’s page, under `docs/reports/`.

## Verification

- Run the focused unit tests.
- Run the live command against the ProductTank San Francisco events repository.
- Render the saved snapshot a second time and compare the Markdown bytes.
- Inspect the report against the saved API values and the scannable-writing checklist.

## Animated chart extension

### Goal

Create a square animated GIF that plots the report’s “At a glance” metrics by day. Show cumulative page views and cumulative Git clones as separate lines.

### Design

- Use the saved daily API rows. Do not estimate missing values.
- Match the supplied reference with a dark background, direct end labels, a strong takeaway, sparse grid lines, and a progressive line reveal.
- Use Pillow for deterministic local rendering. Keep animation creation inside the report command so the GIF and report always use the same validated snapshot.
- Write the animated GIF beside the report and source data. Include its size and hash in the invocation log.
- State that clones can include automation. Do not describe a cloning client as a person.

### Verification

- Check cumulative final values against the report totals.
- Render the same snapshot twice and compare the GIF bytes.
- Inspect the first, middle, and final frames at full size.

## Smoothness research

### Comparison

The current GIF is materially less smooth than the supplied Zentrik reference.

| Cause | Current output | Visible consequence |
| --- | --- | --- |
| Frame cadence | 16 frames; moving frames last 80 milliseconds each, or 12.5 frames per second | The endpoint jumps instead of traveling continuously |
| Sampling | Three in-between positions per day | Steep daily changes become large visual steps |
| Rasterization | Lines and text are drawn directly at 720 pixels square | Diagonal strokes show stair-step edges |
| Color encoding | One fixed 128-color palette with dithering disabled | Color is stable, but edge smoothing has too few shades |
| Easing | Linear progress between daily points | Starts, corners, and stops feel mechanical |

The reference appears to use denser frame sampling and smoother edge rendering. Its exact frame rate and encoder cannot be confirmed from the displayed attachment alone.

### External evidence

- The [GIF89a specification](https://www.w3.org/Graphics/GIF/spec-gif89a.txt) stores each frame delay in hundredths of a second. A 40-millisecond delay gives an exact 25 frames per second; 30 frames per second cannot be represented with one constant GIF delay.
- The [Chrome smoothness guidance](https://web.dev/articles/smoothness) explains that repeated frames make motion visibly stutter because displays need a steady stream of meaningful updates.
- [Pillow’s GIF documentation](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#gif) confirms that `duration` controls frame timing. Its `optimize` option removes unused palette colors and marks unchanged pixels as transparent; it does not add motion frames or smooth edges.
- [Gifski](https://github.com/ImageOptim/gifski) uses cross-frame palettes and temporal dithering. Those techniques reduce color flicker and preserve more apparent colors than a single fixed palette.

### Recommended upgrade

1. Render motion at **25 frames per second** with a constant 40-millisecond frame delay. Use about 60–75 moving frames instead of 16.
2. Draw every frame at **three times the final dimensions**, then shrink it to 720 pixels square with Lanczos resampling. This smooths diagonal lines and text edges.
3. Reveal the line by elapsed time, with gentle ease-in and ease-out at the start and finish. Keep the actual daily data points unchanged.
4. Encode the rendered frames with **Gifski** for cross-frame color selection and temporal dithering.
5. Keep the opening and final holds separate from the motion frames so the chart moves at one steady cadence.

### Delivery choices

| Choice | Result |
| --- | --- |
| **Recommended: supersampled frames plus Gifski** | Closest GIF quality to the reference; adds one external command-line dependency |
| Supersampled frames plus Pillow | Much smoother motion and edges without another dependency; palette quality remains lower |
| Animated WebP or video | Best motion and color quality at a smaller size, but it is not a GIF and may preview differently in Slack or GitHub |

## Programmatic media ecosystem survey

### Bottom line

The common production pattern is not “let an agent draw the final chart.” It is:

1. Keep source data in a validated, versioned structure.
2. Turn that data into a small scene or chart specification.
3. Render every frame deterministically from the data, specification, and frame number.
4. Let an agent choose templates, write or revise code, and run tools.
5. Review stills or a low-cost draft before the final encode.

That split keeps numbers and labels reproducible while still using an agent for the creative iteration. It also matches this repository’s existing source snapshot, validation, deterministic replay, and output-hash design.

### Common architectures

| Architecture | Typical stack | Best fit | Main trade-off |
| --- | --- | --- | --- |
| Direct frame renderer | Pillow or Canvas → PNG frames → Gifski and FFmpeg | Small charts, GIFs, deterministic automation | Layout and animation primitives are hand-built |
| Browser chart capture | D3, SVG, and HTML → controlled headless browser clock → PNG frames → FFmpeg | Existing web charts and rich SVG and CSS | Browser and font reproducibility require discipline |
| Component video renderer | Remotion and React → frame-based compositions → MP4 or GIF | Reusable branded templates, many aspect ratios, audio, batch video | Larger JavaScript toolchain and Remotion licensing review |
| Vector explainer engine | Motion Canvas or Manim → video | Narrated explainers, diagrams, mathematical animation | More framework-specific scene code than this chart needs |
| Static social-card renderer | Satori and JSX → SVG → Resvg and PNG | Covers, thumbnails, Open Graph cards | Static output; animation needs another renderer |
| Agentic production system | Agent → scene plan and assets → deterministic renderer → approval gate | Multi-scene productions with mixed media | Broad tool surface, provider cost, and more failure modes |

The durable boundary is the same across these stacks: the renderer receives structured facts and an explicit timeline. The model may propose the scene plan, but it should not invent pixel positions, data values, or labels at final-render time.

### Evidence from working tools and repositories

- [Remotion](https://github.com/remotion-dev/remotion) treats React code as the source of truth and supports programmatic, interactive, and batch rendering. Its official [dataset-rendering guide](https://www.remotion.dev/docs/dataset-render) passes JSON records into reusable compositions as typed input properties. This is the strongest fit when one chart becomes a family of branded videos.
- [render-d3-video](https://github.com/russellsamora/render-d3-video) overrides the browser clock, captures exact frames in a headless browser, and uses FFmpeg for output. Its stated advantage over screen recording is deterministic frame-by-frame rendering without runtime jank.
- [Veltman’s data-animation experiments](https://github.com/veltman/gifs) compare screen capture, Canvas, SVG, browser capture, and frame-by-frame rendering. The recurring trade-off is repeatability versus implementation complexity: explicit frame generation is automatable and precisely timed; screen capture is easy but manual and hard to reproduce.
- [Motion Canvas](https://github.com/motion-canvas/motion-canvas) combines a TypeScript generator-based animation library with a real-time editor. It is optimized for informative vector animation and voice-over synchronization.
- [Manim](https://github.com/3b1b/manim) is a Python engine for precise explanatory animation. It is proven for mathematical scenes, but introduces OpenGL, FFmpeg, and optional LaTeX dependencies that do not help this simple traffic chart.
- [Satori](https://github.com/vercel/satori) converts a constrained JSX and CSS tree into SVG and is commonly paired with a rasterizer for social cards. It is useful for static covers or report previews, not for the animated line itself.
- [OpenMontage](https://github.com/calesthio/OpenMontage) demonstrates a broad agentic pattern: analyze a reference, preserve named aspects such as pacing and structure, produce concepts and cost estimates, then stop at a storyboard approval gate before expensive generation. Its scope is much larger than this report, but the reference-analysis and approval-gate pattern is reusable.

### Practitioner patterns

The implementation write-ups converge on a reference-first, draft-review-final loop:

- A [Substack Remotion walkthrough](https://louisedesadeleer.substack.com/p/how-i-make-custom-motion-graphics) saves visual references, asks the coding agent for a minimal first pass, then iterates with small visual corrections. It also recommends supplying real CSV or spreadsheet data rather than asking the model to fabricate chart content.
- A [Medium production write-up](https://medium.com/@emergentcap/how-i-added-ai-video-production-to-claude-code-in-one-afternoon-9edcb68853aa) uses a JSON list of narrative beats to drive reusable Remotion compositions. The agent writes code and render properties; the human reviews the result.
- A [Substack postmortem](https://wonderingaboutai.substack.com/p/i-built-a-video-post-production-pipeline) found that a rigid CLI was premature while the editing process still required frequent one-off adjustments. Its successful hybrid used Puppeteer for deterministic HTML and CSS cards, FFmpeg for assembly, generated art only for non-text imagery, and a conversational agent for orchestration. The author recommends formalizing automation only after repeated decisions stabilize.
- Reddit discussions are directionally consistent but anecdotal. Creators describe reusable scene primitives, structured storyboards, draft renders, and repeated visual review in [Remotion launch-video workflows](https://www.reddit.com/r/ClaudeAI/comments/1tik0qe/coffee_claude_and_remotion_is_all_you_need_to/) and [automated app-preview workflows](https://www.reddit.com/r/indiehackers/comments/1r43r7g/my_workflow_for_generating_app_store_preview/). GIF-focused threads report that [Gifski improves color quality at the cost of larger files and slower encoding](https://www.reddit.com/r/rust/comments/7ahvog/gifski_highestquality_gif_converter/). Treat these reports as workflow ideas, not benchmark evidence.

### Recommended architecture for this chart

Keep the current Python renderer. Moving one square line chart to React, a browser, or a video framework would add installation, licensing, and reproducibility work without fixing a problem that higher frame density, easing, supersampling, and a better GIF encoder already solve.

Use this pipeline:

```text
GitHub API snapshot
  → schema and total validation
  → cumulative chart series
  → deterministic frame state from elapsed time
  → 3× Pillow render
  → Lanczos downsample
  → Gifski encode
  → report, GIF, source snapshot, and hashes
```

Agentic behavior belongs around that pipeline:

- Compare the supplied reference and name the visual properties to preserve.
- Modify the renderer or theme, never the source values.
- Generate first, middle, peak, and final review frames before the full encode.
- Check totals, labels, contrast, clipping, and motion cadence.
- Require human visual approval when the design changes materially.
- Promote a visual decision into a reusable option only after it recurs.

### When to change stacks

- Adopt **Remotion** when the output expands to multiple reusable video templates, aspect ratios, narration, synchronized captions, or batch variants. Review its custom license before adoption.
- Adopt **D3 plus deterministic browser capture** when the canonical chart already exists as an SVG or HTML visualization.
- Adopt **Motion Canvas** when voice-over-synchronized vector explanation becomes the primary product.
- Adopt **Manim** for mathematical or geometry-heavy explanation.
- Add **Satori and Resvg** only when static social cards or thumbnails become a separate required artifact.
- Prefer MP4 or animated WebP over GIF when the destination reliably previews them; GIF’s palette and 10-millisecond timing units remain hard quality limits.
