# Talk Notes

From Voice Memo to Production-Ready Code
Tom Alterman · ProductTank SF · September 30, 2026

These are the speaking notes for the deck in `slides/`, in slide order.

## Opening

Tonight I'm going to walk through how I use a combination of tools to go from a rough idea to a production-ready pull request. This is a casual, practical walkthrough from someone building real software with AI, not expert doctrine.

Two warnings up front. We're all figuring this out as we go. And don't trust anyone who calls themselves an AI expert, including me. Everything here is changing fast, and most of us are learning by trial and error.

## The stack

Five tools, and I'm not married to any of them.

1. Claude Code is the agent. Or Codex, or Cursor, or whatever is good this month. I use strong models and don't over-optimize for token cost in my own work.
2. GitHub is the source of truth. It's also where context accumulates over time.
3. Compound Engineering is the secret sauce. An open-source plugin from Every that encodes good engineering practice as reusable skills.
4. Monologue, also from Every, is voice dictation that turns speech into clean writing instead of a raw transcript. I record long, rambling brain dumps and feed them straight to the agent.
5. Impeccable is a design skill for when the UI actually matters.

## What Compound Engineering is

A group of very conscientious engineers sat down and encoded the entire process from idea to shipped, maintained product. The philosophy is 80 percent planning and review, 20 percent execution.

Imagine the A-plus version of yourself who thought carefully about what good brainstorming, good planning and good code review look like, and wrote it all down as repeatable workflows.

The net effect is that it behaves like an incredibly talented, hard-working, patient engineering team, and I get to be the world's laziest product manager.

## The loop

There are 36 skills in the plugin. These are the six I use most.

- `/ce-brainstorm`: what does this need to be? An interactive Q&A that asks you one decision at a time and writes real requirements. This is where the voice memo goes.
- `/ce-plan`: what's needed to accomplish this? Turns requirements into an implementation-ready plan.
- `/ce-work`: build it, with verification and commits.
- `/ce-code-review`: a multi-persona review against the plan. Several reviewers, different concerns, and you pick which notes to take.
- `/ce-commit-push-pr`: commit, push, open the PR.
- `/ce-compound`: write down what was learned so the next loop starts smarter. This is the part that makes it compound. Run one teaches it, run two remembers.

Also in the toolbox:

- `/ce-prototype` when I need people to feel the thing before we commit. It builds a throwaway, then writes the decisions back into the plan.
- `/ce-debug` when I'm starting from a bug, a screenshot, or a customer complaint. Root cause with a causal chain, then an optional fix and PR.
- `/ce-babysit-pr` once the PR is open. Watches it, handles review comments, fixes CI. Never merges on its own.

And then there's `/lfg`. The whole pipeline, hands off: plan, build, simplify, review and apply the fixes, run browser tests, commit, push, open a PR, watch CI. It does not merge unless you tell it to. The trick is to always run `/ce-brainstorm` first so it's planning against real requirements rather than a one-line prompt.

## Live example

This is from this morning. The idea: demo pages for contractor sales calls that reskin themselves based on the contractor's own website, so the demo feels built for them instead of generic.

The input was a rough brain dump, not a spec.

1. Pasted it in and ran `/ce-brainstorm`.
2. It read the notes, inspected the codebase, and asked follow-up questions to pin down what I actually wanted.
3. It wrote a detailed plan. Very technical, too dense for me to consume directly.
4. I asked for a simpler, more visual, product-level explanation of the plan.
5. I answered a handful of decision questions and told it to proceed.
6. It spent about 40 minutes building and testing. Before it started I told it not to come back until the work had been tested in the browser, checked visually, and brought to a high standard.

Over time the workflow builds its own internal wiki about how to work with me and inside this codebase: lessons from past tasks, preferred patterns, mistakes to avoid. I didn't write most of it. It came out of the compound step and only needs correcting when it drifts. Even when context resets, the next agent still knows the standards.

## Takeaways

Tools change. The bottleneck doesn't.

The hard part was never the code. The hard part is deciding what to build, explaining it clearly, and getting other people to agree.

AI makes PM quality visible. The workflow exposes whether you understand the problem, whether you can articulate the strategy, and whether you can define success. A painful lesson: many of the implementation failures PMs blame on engineering come from the PM's own vague, incoherent, or incomplete instructions.

## Q&A: should PMs write production code?

Not always. When engineers are available it's often not the highest-leverage use of a PM's time. But there are cases where it clearly is: turning an idea into a real interactive prototype inside the actual product, skipping a long handoff cycle for a straightforward and well-scoped change, producing a working PR instead of just a spec or ticket, and shortening the wait between idea and experiment.

In a previous setup, tickets were auto-generated from meetings, reviewed quickly, and sent off to build automatically. That's how far it can go in the right environment.

## Links

- https://github.com/EveryInc/compound-engineering-plugin
- https://every.to/guides/compound-engineering
- https://monologue.to
- https://impeccable.style
