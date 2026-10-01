# Overview: HarnessTax: How Much Does the Harness Matter for Coding Agents?

**Source:** HarnessTax blog (UC Berkeley · Arena Intelligence Inc.; Melissa Z. Pan, Shuo Yang, Negar Arabzadeh, Wei-Lin Chiang, Ion Stoica, Matei Zaharia) · https://harnesstax.github.io/
**Claim:** Swapping the harness around a coding model barely changes how many tasks it solves, but it can change the cost by up to 5x. The authors call this hidden cost a "harness tax."

## Three Headline Findings

The authors report three findings on two open-source benchmarks, in this order:

1. **"Harness choice has little effect on task success rate, but can significantly affect the cost"**: the same model reaches similar success at up to 5x the cost.
2. **"A simple harness can be competitive"**: Pi is minimal and open-source.
3. **"Models may perform better with other harnesses than with their own."**

- Verbatim: "So it turns out that your Claude models may not need Claude Code…"

The authors say they will publicly release their profiling traces, which are logs of each run.

→ **Deeper:** each finding's evidence and figure, tied back to its headline claim · anchor: "Our study reveals three surprising findings"

## Study Design and Benchmarks

A **harness** is the software around a model. It gives the model tools, decides what context it sees, and runs the task. The study pairs 7 models with 3 harnesses (Claude Code, Codex CLI, Pi), for 21 model–harness pairs.

| Setting | Value |
|---|---|
| Benchmarks | SWE-bench Lite, Terminal-Bench 2.0 |
| Tasks | 30 randomly sampled per benchmark |
| Attempts | 3 per task |
| Turn cap | 100 agent turns |
| Effort | each harness's high setting |
| Error bars | 95% intervals from 10,000 bootstrap resamples, meaning the data is resampled many times to estimate uncertainty |
| Pricing | fixed direct-API list dated September 1, 2026 |

The prose names only some models. The live charts list all seven:
- Claude Fable 5
- Claude Opus 4.8
- Claude Sonnet 4.6
- Claude Haiku 4.5
- GPT-5.6 Luna
- GPT-5.6 Sol
- Kimi K3

→ **Deeper:** full protocol, including the network block on SWE-bench Lite, Pi's two add-on packages, and Kimi K3 via Fireworks AI · anchor: "Experiment Setup"

## Harness Tax on Cost

The same model gets about the same score at very different prices. For example, Claude Fable 5:

| Harness | Success | Cost per attempt |
|---|---|---|
| Claude Code | 97.8% | $1.33 |
| Codex | 96.7% | not stated |
| Pi | 96.7% | $0.67 |

Across shared models, using the geometric mean of cost ratios (the typical multiple):
- On SWE-bench Lite, Claude Code costs about **2.0×** Pi and **1.6×** Codex
- On Terminal-Bench 2.0, Claude Code costs about **1.5×** Pi
- The harness changes success rate by at most ±2% on SWE-bench Lite and about ±5% on Terminal-Bench 2.0

Model results by name:
- GPT-5.6 Luna is the cheapest on both benchmarks
- Fable 5 has the top success rate on SWE-bench Lite
- Kimi K3 is open-weight, meaning anyone can download it, and lands near the best-value line

### Harness Tax

This is the paper's coined term: paying more for about the same quality only because of which harness wraps the model. The term comes from Siddharth Sambharia's Portkey post, "The Harness Tax: The Dead Weight Inside Your Coding Agent" (April 13, 2026).
- Verbatim: "when you accept a coding agent’s default harness without comparing alternatives"

→ **Deeper:** cost ratios for each model and harness, plus the authors' recommendation to evaluate every model across harnesses · anchor: "Finding 1/3: Harness affects cost more than correctness"

## Pi's Minimal Four-Tool Harness

Pi reaches the best-value line on both benchmarks with just four tools:
- read
- write
- edit
- bash

The authors take this to mean researchers can build competitive harnesses with existing models. They would not need a proprietary harness or a model trained alongside its harness. They also add a counterweight: richer harness features may still help other models, workloads, or interaction settings.
- Verbatim: "Harness complexity should therefore be treated as an empirical trade-off."

### Pareto Frontier

This is the stepped line in Figure 1. At each cost level, it marks the highest success rate observed at or below that price. A pair on the line is the best buy at its price. Figure 1 is a live interactive chart with one view per benchmark, so it is not reproduced here.

→ **Deeper:** the frontier points for each benchmark and where each pair sits relative to the line · anchor: "Finding 2/3: A simple harness can be competitive"

## Sources of the Cost Gap

The authors point to two places where extra spending shows up. They do not give a full breakdown of total cost.

| Signal | Finding | Figure |
|---|---|---|
| Cost per turn | On SWE-bench Lite with Fable 5, Pi averages 15.4 turns and Claude Code 15.3. Claude Code costs about 2× as much for a 1.1% success gain. | Figure 2: cumulative cost–success curves |
| First model call | Across all seven models, Claude Code's mean initial context is over 10× Pi's, with longer instructions and larger tool schemas | Figure 3: first-call context on SWE-bench Lite |

**Initial context** is everything sent to the model before it starts working: instructions, tool descriptions, and the task.
- Verbatim: "A harness tax can begin with the first model call."

Figures 2 and 3 are live charts and are not reproduced here.

→ **Deeper:** the per-turn spending comparison and the instruction and tool-schema sizes for each harness · anchor: "A harness tax can begin with the first model call"

## Models Outside Their Home Harness

The provider's own harness is often not the best fit for its own model. Across the six Anthropic and OpenAI models on both benchmarks, a different harness has the top success rate in **nine of twelve comparisons**.

| Model | Benchmark | Own provider's harness | Better alternative |
|---|---|---|---|
| Sonnet 4.6 | SWE-bench Lite | Claude Code 66.7% | Codex 68.9%, similar cost |
| GPT-5.6 Sol | Terminal-Bench 2.0 | Codex 78.9%, $0.76 | Pi 83.3%, $0.42 |

The authors weigh this against OpenAI's description of GPT-5-Codex as optimized for software engineering in Codex. Figure 4 shows cost and success for each model with 95% whiskers. It is a live chart and is not reproduced here.

→ **Deeper:** the full results for all twelve comparisons, showing which harness won for each model · anchor: "Finding 3/3: Models can perform competitively outside their own harness"

## Stated Limitations

The authors name these limits on how far the results reach:
- Only two open-source benchmarks were tested
- Each harness defines a "turn" differently, so turn counts are not directly comparable
- Initial context is only one cost driver; caching, generated tokens, and later calls also count
- Richer harness features may still help other models, workloads, or interaction settings

- Verbatim: "which the models may have encountered during training"
- Verbatim: "Results may differ on other benchmarks and workloads."

→ **Deeper:** each caveat linked to the finding it weakens · anchor: "Ending Notes"

## Harness Research Agenda

The authors name the next step: evaluate harnesses and automate harness selection in real development workflows, where:
- requirements evolve
- developers provide feedback
- tasks extend across sessions

| Task type | What the harness should prioritize |
|---|---|
| Day-to-day coding | cost efficiency and reliability |
| Harder problems, including scientific discovery | structured guidance for exploring ideas, evaluating candidates, and learning from feedback |

- Verbatim: "We should envision a redesigned harness that adapts as tasks unfold while remaining general."

Related prior work by the authors: retrieval agents, arXiv:2605.27361.

→ **Deeper:** the authors' view of coding agents as interfaces to model intelligence, and what that means for harness design · anchor: "The natural next step is to evaluate harnesses"

---

**Shape check:** 8 `##` themes, 2 `###` constructs, 8 hooks.
