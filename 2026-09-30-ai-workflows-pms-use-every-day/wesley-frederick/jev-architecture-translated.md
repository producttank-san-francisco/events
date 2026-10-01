# Jev Architecture: Translated

*A plain-English reading of Archer Hume's essay "[Jev's Architecture Unmasked](https://archerhume.com/posts/jevs-architecture-unmasked)" (17 September 2026).*

Ask a chatbot whether a support ticket is urgent and how sure it is, and it might reply, "Urgent, 90% confident." That reads like a measurement. It isn't one. The model wrote "90%" the same way it writes any sentence: by predicting which characters should come next. As Hume puts it, the model's probability of producing those words does not establish a 90% probability of being right.

Teams still build fraud screens, moderation, and ticket routing on that pattern. They pay a model to type its answer out piece by piece, then treat a typed-out confidence as a number their software can act on.

**Jev**, a decision model from a company called TypeSafe, claims to fix both problems. TypeSafe hasn't released its weights or its research, so Hume sent about 10,000 API calls at it and worked backward from what came out. On X, people waved it off as "a JSON classifier." His essay argues they missed the point. Let's dig in.

## Picture a reading test

The easiest way I've found to hold Jev in your head is a school reading-comprehension exam.

You get one passage. Below it sit several questions, each with a short list of answers. One twist: you never write an answer out. You shade bubbles, and you can shade them partway. Shade "payments" 91% and "account" 6%, and that shading is your answer.

Jev's interface maps onto that exam almost exactly. You send three things. The **state** is the passage: a customer message, an incident report, a transaction log. The **questions** are what you want decided, such as "Which team should handle this?" or "Does this need a human right now?" The **allowed answers** are the bubbles: a list of choices, a yes/no, or a level on a scale. Jev hands back a probability for every bubble on every question, all at once.

Hume's reconstruction has five working parts, and each one fits a rule of that exam.

## Read the passage once

A student facing fifty questions about one passage doesn't reread it fifty times. They read it once and keep it in mind.

Transformers can do the same. As a model reads, it saves working notes on every word in a **KV cache** (key–value cache). In other words, the KV cache is the model's notebook for text it has already read. Hume's evidence suggests Jev fills that notebook for the state once, then lets every question consult it. With $S$ state tokens and $Q$ questions, the repeated reading shrinks from $Q \times S$ to $S$.

The clearest evidence sits in Jev's size limits. Each question, together with the state, can run to about 32,768 tokens; a whole request can run to about 65,536, and the state counts only once toward that total. A 23,000-token state with 5,000 questions fit. If every question had carried its own copy of the state, that request would have topped 100 million tokens. Speed tells the same story: server time barely moved up to about 100 questions, and 1,500 questions still came back in a few hundred milliseconds.

## Each question gets its own answer sheet

Now the exam rule that keeps things fair: while answering one question, you can't read the others.

Hume tested this with a secret. He planted "The secret code for this request is ZEBRA-7741" inside one question, then asked a second question which code the other question had mentioned. Jev gave ZEBRA-7741 a probability of 0.00. When he moved the same sentence into the shared state, the probability jumped to 0.90–0.92, across five repeats each.

Why build that wall on purpose? Asking "Is this customer angry?" shouldn't change which team gets the ticket. Each question sees the same evidence and nothing else. Hume stays careful here: the test shows the questions *behave* as if isolated, but it can't reveal the exact wiring that keeps them apart.

## Shade, don't write

This is where Jev parts ways with a chatbot. A chatbot answers by writing: predict one token, feed it back in, predict the next, repeat. Spelling out `"payments": 0.91` takes a chain of those steps, and each step waits on the one before.

TypeSafe's own launch post says Jev "outputs all probabilities in parallel instead of autoregressively generating by token." Hume's reading: once the model finishes reading, a small final math layer called a **readout** turns its internal state into one score per allowed answer. A standard formula then converts those scores into probabilities that add up to one. Ordinary code wraps the numbers in JSON afterward.

His sharpest confirming evidence came from the bill. The API reports a field called `output_tokens`, which sounds like a count of written text. It isn't. The count grows with the length of each question's ID, and TypeSafe's docs say that ID "is not sent to the underlying model." An answer of 0.0 costs the same as 0.01. A question with 200 options, billed at 1,911 output tokens, came back as fast as a question with two. The field is a billing figure computed after the fact, not a trace of writing.

## Read every option before choosing

Within one question, the bubbles do affect each other. A good test-taker reads every option before picking; "none of the above" means nothing without the rest of the list.

Hume tested this with a deliberately silly option. He asked what caused a payout failure and offered four answers: bank, provider, customer, unknown. Then he appended "Bad weather caused it." If Jev scored each option on its own, adding a fifth couldn't change the odds between "customer" and "unknown"; the math cancels out. The odds moved anyway. Across ten randomized rounds, the customer-versus-unknown log-odds (a measure of how far the scale tips toward one side) fell from +0.38 to +0.11, and they dropped in every round.

The flip side will feel familiar to anyone who has written a multiple-choice test: order matters. Reversing the options on one support ticket moved a probability from about 0.84–0.89 to 0.93–0.96. If your rule says "act above 0.9," the same ticket with the same evidence could trigger different actions depending on how you listed the choices. Hume's advice is to shuffle option order when you evaluate.

## Grade against the answer key

Cheap shading is worthless if the shading is wrong. The test that matters is **calibration**: of all the answers shaded 80%, do about 80% turn out right?

TypeSafe calls its training method **Reinforcement Learning for Calibrated Decisions**, or RLCD, and keeps the recipe private. Hume points to the kind of grading that rewards honesty. Log loss and Brier loss are **proper scoring rules**, which means a student earns the best score over time by shading exactly as sure as they really are. Bluffing high costs points; hedging low costs points too. He's explicit that this explains the goal of such training, not the loss TypeSafe actually uses.

The results look encouraging, within limits. On 1,200 questions from the MMLU benchmark, stated probability and actual accuracy differed by about three points on average (an expected calibration error of 0.031). On freshly generated three-digit multiplication, Jev was right 86.7% of the time with an average top probability of 0.83. On harder two-step word problems it was right 32% of the time at 0.30. It grew less sure as it grew less accurate, which is what you want. One family broke the pattern: modular exponentiation, right 56% of the time at a stated 35%.

Watch one trap. The API's `confidence` field isn't a second, learned opinion. It's arithmetic on the shading that measures how far the top answer stands above an even split. Three options with a top probability of 0.8 yield a confidence of 0.7. A sharply shaded answer can still be confidently wrong.

## What you can't see from outside the exam hall

Hume can watch the answer sheets and time the students. He can't look inside their heads.

He assumes Jev is a **causal decoder**, the left-to-right reader behind GPT-style models, mainly because Jev's 84.6% on the harder MMLU-Pro benchmark implies very large-scale pretraining, and every model at that scale is built this way. His tests can't rule out the alternative. Jev's tokenizer, the rule for chopping text into pieces, matched none of the 192 public tokenizers he tried; the closest, Qwen's, agreed on 348 of 415 probes.

He goes one step further and expects Jev to be a **sparse mixture-of-experts** model. Think of a hospital that routes each patient to two or three specialists instead of the whole staff: the hospital employs many doctors, but any one visit uses only a few. A sparse model works the same way, sending each token through a small subset of its sub-networks. His reasons: Jev read about 30,000 tokens in roughly 160 milliseconds, where a conventional 70-billion-parameter model on a top-end eight-GPU server would need around a second. A model with about 10 billion active parameters fits that speed. A model that only reads, never writes, is limited by raw computation, which is exactly what sparse routing saves. And most of today's strongest open base models, such as DeepSeek-V3, Qwen3, and Kimi K2, use this design.

Hold that conclusion loosely. Hume labels it an inference, not an observation: specialized hardware could let a conventional model match the speed, and confirming it would take a disclosure from TypeSafe. He also notes that nothing else in his reconstruction depends on it. Swap in a conventional model and the passage, the separate answer sheets, and the shading all stay the same.

## So, what can we take away?

Hume ranks his own claims by strength. The parallel probability outputs are published by TypeSafe. The question isolation and the order effects are behavior he observed. The shared notebook, the exact readout design, and the sparse experts are progressively more speculative explanations of that behavior.

For anyone designing an AI workflow, I'd argue the practical lesson is about shape. When a step is a choice among known options, perhaps you don't need a model to write anything. Ask for a distribution, then let code apply the policy. If a needless escalation costs one unit and a missed urgent case costs nine, a simple rule escalates whenever the chance of urgency tops 0.1. That rule only means something if the probabilities hold up on your own cases, so test calibration on your data, shuffle option order, and expect small differences between identical calls. If one question truly needs another's answer, add a second stage; separate answer sheets can't pass notes.

Hume closes on the same idea: a decision service needs to read evidence, compare permitted outcomes, and show its uncertainty, and a transformer can do all of that without turning every decision into a sentence first. I hope the exam hall makes that easier to picture.
