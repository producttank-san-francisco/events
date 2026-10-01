# Overview: Jev’s Architecture Unmasked

**Source:** archerhume.com (Archer Hume · essay, 17 September 2026 · 28 min read) · https://archerhume.com/posts/jevs-architecture-unmasked
**Claim:** Probing TypeSafe's closed Jev API with about 10,000 calls points to "a causal transformer (likely using sparse MoE) repurposed for decisions": the input is read once, each question is answered separately, and answer probabilities are read straight from the model instead of written out as text.

## Generated Confidence vs. Read-Out Probability

An ordinary LLM writes "90% confident" as text, and those words are not a real probability that software should act on. Jev claims to fix this. It reads decision probabilities from the model's internals and trains them against real outcomes. You send shared **state**, a set of **questions**, and allowed answers. You get back a probability for every answer, all at once, with no text written.

- Verbatim (X take the author rebuts): "12 million views for a JSON classifier? Yeah, we’re in a bubble."
- Schematic example (numbers invented by the author): `payments` 0.91, urgent escalation 0.42
- Cost rule example: if a needless escalation costs 1 and a missed urgent case costs 9, escalate when p(urgent) > 0.1
- Verbatim: "None of this requires diffusion."

Figure 1, the proposed computation diagram, is an image and is not reproduced here.

→ **Deeper:** the support-routing JSON example, the difference between text generation and a direct readout, and the cost-weighted decision rule · anchor: "Why this design is useful"

## Direct Probability Readout

Jev appears to end with a **readout**, a small math layer that turns the model's final internal state into answer scores. Older chatbots write the answer one token at a time; this skips that loop.

- Published: "Jev outputs all probabilities in parallel instead of autoregressively generating by token."
- Observed: `output_tokens` is a billing number, not a record of generated text. It equals 4 shared + 15 per answer + the length of each question's ID, and the ID "is not sent to the underlying model"
- An answer of `0.0` costs the same as `0.01`
- 200 options (1,911 output tokens) returned as fast as 2 options. A 255-option response reported 2,714 output tokens
- Formula (verbatim): $z = Wh + b, \qquad p_i = \frac{e^{z_i}}{\sum_{j=1}^{K} e^{z_j}}$, which turns scores into probabilities that sum to 1

### Option Slots

These are numbered answer positions ("first option, second option, third option") rather than fixed labels like "payments". Application code maps each slot back to the caller's own option key.

→ **Deeper:** the published-vs-observed evidence, the token-billing breakdown, and the slot head vs. reserved-label-token designs · anchor: "1. End inference with a readout"

## Shared State, Isolated Questions

The state is processed once and every question reads it, but questions cannot see each other. The **KV cache** (key–value cache) is the model's saved work on text it has already read. Sharing it means the state is processed once, not once per question: with $S$ state tokens and $Q$ questions, the cost drops from $QS$ to $S$.

- Token counts add up exactly: 1 yes/no question = 268 input tokens, two = 276, a mixed three-question request = 318
- Secret-code probe `ZEBRA-7741`, 5 repeats per condition:

| Where the secret sat | Probability it was found |
|---|---|
| Sibling question | 0.00 |
| Sibling removed | 0.00 |
| Shared state | 0.90–0.92 |

- Server time was flat up to about 100 questions. Per token, question text cost roughly twice as much as state
- Limits: about 32,768 tokens per branch and 65,536 per request. A 23k-token state with 5,000 questions still fits

Figure 2 (latency charts) is an SVG and is not reproduced here.

→ **Deeper:** the visibility probe, latency sweeps, context limits, and the Hydragen/DeFT prior art · anchor: "2. Share the state, isolate the questions"

## Causal Backbone and Tokenizer

The author assumes Jev is a **causal decoder**, a model that reads text left to right like GPT-style LLMs. The tests themselves cannot rule out a model that reads in both directions. Reasons given:

- 84.6% on MMLU-Pro implies frontier-scale pretraining, and every model at that scale is a causal decoder
- TypeSafe describes RLCD as post-training of a pretrained language model
- A bidirectional model would give up shared-prefix caching

The tokenizer (how Jev splits text into units) matches none of the 192 public tokenizers tested across 415 probes. Closest match: Qwen, at 348 of 415.

Reference-card test (the card holds the fact that decides which option is correct):

| Card position | Correct |
|---|---|
| First | 12 / 16 |
| Middle | 11 / 16 |
| Last | 16 / 16 |
| Moved into state | 48 / 48 |

Figure 3 (interactive probability chart) is not reproduced here.

→ **Deeper:** the decoder-vs-encoder argument, tokenizer fingerprint quirks (o200k, digit splitting), and the reference-card templates · anchor: "3. A causal backbone"

## Option Interaction Within Questions

A question's options are read together as one list before a single decision, so they affect each other. Test: four payout-failure causes (`bank`, `provider`, `customer`, `unknown`), then add `weather: Bad weather caused it`. If each option were scored on its own, the odds between `customer` and `unknown` would not move.

| Study | Shift in customer-vs-unknown log-odds |
|---|---|
| Original | +0.49 → +0.08 |
| Replication, 10 randomised blocks | +0.38 → +0.11; mean −0.28; 95% interval −0.36 to −0.19 |

- Swapping in "Wild birds caused it": inconclusive (interval included zero)
- Cap: 255 options (2⁸ − 1), enforced by request validation
- Fake injected options never displaced real ones
- Reversing option order moved one probability from 0.84–0.89 to 0.93–0.96, enough to cross a 0.9 threshold

### Pointer-Style Scorer

The rival to option slots. It scores each option by comparing the decision against that option's own internal representation. Neither design is ruled out.

Figure 4 (per-block odds chart) is not reproduced here.

→ **Deeper:** the irrelevant-option replication, slot vs. pointer evidence, the FIRST listwise-ranking prior art, and why order effects matter for thresholds · anchor: "4. Let the options interact before choosing"

## Outcome-Trained Calibration

A cheap probability can still be a wrong one. **Calibration** means that of all predictions at 0.8, about 80% turn out right.

### Reinforcement Learning for Calibrated Decisions

This is TypeSafe's name for its training method, RLCD. The exact recipe is unpublished.
- Verbatim: "answers with epistemically honest probabilities on System One tasks"

### Proper Scoring Rules

These are losses, like log loss $-\log p(y)$ and Brier loss, where reporting your true belief gets the best expected score. They show what such training aims for, not which loss TypeSafe actually uses.

| Test | Result |
|---|---|
| MMLU sample, 1,200 items | ten-bin ECE 0.0313; 990 items in the 0.9–1.0 bin |
| Three-digit multiplication | 86.7% accuracy, average top probability 0.83 |
| Two-step word problems | 32% accuracy, 0.30 |
| Modular exponentiation | right 56% at mean probability 35% |

- Verbatim: "That gap does not establish benchmark contamination."
- The API's `confidence` field is plain arithmetic, not a learned estimate: $c = \frac{p_{\max}-1/K}{1-1/K}$. Three options with a top probability of 0.8 give 0.7

Figure 5 (reliability charts) is an SVG and is not reproduced here.

→ **Deeper:** what RLCD is said to do, scoring-rule theory, the calibration bins, and the `confidence` formulas for Choice and Score · anchor: "5. Train the distribution, then calculate confidence"

## Sparse Mixture-of-Experts Backbone

The author infers, without being able to observe it, that Jev is a **sparse mixture-of-experts (MoE)** model. In an MoE, a router sends each token through a few of many sub-networks, so only part of the model runs for each token. Supporting points:

- Jev processed about 30k tokens in roughly 160 ms. A dense 70B model on an 8×H100 node would need around a second, while an MoE with about 10B active parameters fits that speed
- A model that only reads input is limited by compute, which is exactly what sparse routing saves
- Strong recent base models are MoE: DeepSeek-V3, Qwen3, GLM-4.5, Kimi K2, gpt-oss

Caveats: specialised hardware could let a dense model match that speed. Nothing else in the reconstruction depends on MoE.

→ **Deeper:** the compute-bound argument, the latency arithmetic, and the counter-evidence · anchor: "6. Sparse capacity"

## Branches as a Batch

Each question is an independent work item, packed into batches that read the shared state. Application code then attaches question IDs and builds the JSON response.

- Identical repeated questions gave slightly different answers, even within one request, so do not assume determinism (`noise`, `dup`, `determinism` probes)
- Response key order varied in a few recurring patterns. Multiple workers are a plausible cause, but this reveals nothing about worker count, cache location, or numeric precision
- If one question truly needs another's answer, the application must add a second stage

→ **Deeper:** sources of nondeterminism, what the key-order side channel can and cannot reveal, and the limit on answer dependencies · anchor: "7. Schedule branches as a batch, not a conversation"

## Evidence Tiers and Methods

The author ranks his claims by how well supported they are, in this order:

1. Direct probability outputs: publicly described by TypeSafe
2. Question isolation and option-order effects: observed behaviour
3. KV sharing, causal attention, final-position or pointer-style readouts, sparse experts: "progressively more specific explanations"

| Methods item | Value |
|---|---|
| Model / date | `jev-1.13.0`, 17 September 2026 |
| Access | one early-access account, one service region |
| Source study | 1,029 probe records (incl. 190 generated-math items); 6,800 benchmark records |
| Follow-ups | 146 relational/option-interaction, 311 token-accounting, 445 tokenizer, 192 latency, 148 option-count latency, 181 option-position, 105 fake-option, 35 context-limit |
| Latency source | `x-envoy-upstream-service-time` header, on a shared server |

→ **Deeper:** the open tests that would change the conclusion (e.g., a middling-difficulty 200-option task to tell slot from pointer) and the downloadable evidence bundle · anchor: "What would change my mind?"

---

**Shape check:** 9 `##` themes, 4 `###` constructs, 9 hooks.
