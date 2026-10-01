# Tom Alterman

Director of Product, GoodLeap; founder, Tomek.io

**Talk:** Using AI to take a product idea from concept to pull request

**Event:** [AI Workflows PMs Use Every Day](https://github.com/producttank-san-francisco/events/tree/main/2026-09-30-ai-workflows-pms-use-every-day) — September 30, 2026, at Cribl, San Francisco

## Links

- **Slides:** [PDF](slides/from-voice-memo-to-production-ready-code.pdf) · [PowerPoint](slides/from-voice-memo-to-production-ready-code.pptx)
- **Cheat sheet:** [CHEATSHEET.md](CHEATSHEET.md), the commands and install steps on one page
- **Talk notes:** [TALK-NOTES.md](TALK-NOTES.md), the talk script in slide order
- **Resources:** [Compound Engineering](https://github.com/EveryInc/compound-engineering-plugin) · [Compound Engineering guide](https://every.to/guides/compound-engineering) · [Monologue](https://monologue.to) · [Impeccable](https://impeccable.style)

## Summary

How a product manager goes from a rough idea to a production-ready pull request using AI coding agents and a structured workflow.

This folder contains the slides, a plain-language guide to the approach, a one-page command cheat sheet, and the talk notes. It is written for PMs, not engineers. Nothing here requires you to know how to code.

A warning before anything else: we are all figuring this out as we go. The tools in this guide will be replaced by better ones. Don't trust anyone who calls themselves an AI expert, including me. Treat this as one person's working setup, not doctrine.

## The one-sentence version

The hard part of building software was never the code. It is deciding what to build, explaining it clearly, and getting other people to agree. AI agents make the code part cheap, which means the quality of your product thinking is now the thing on display.

## The stack

Five tools. I am not married to any of them, and I swap them when something better comes along.

| Tool | What it does | Link |
|---|---|---|
| Claude Code | The coding agent. Interchangeable with Codex, Cursor, or whatever is good this month. Use strong models; for personal work, don't over-optimize for token cost. | https://claude.ai/code |
| GitHub | The source of truth. Also where context accumulates over time. | https://github.com |
| Compound Engineering | The secret sauce. An open-source plugin from Every that encodes good engineering practice as reusable skills: brainstorming, planning, prototyping, review, PR handling, and learning from past work. | https://github.com/EveryInc/compound-engineering-plugin · https://every.to/guides/compound-engineering |
| Monologue | Voice dictation that turns speech into clean writing, not a raw transcript. Also from Every. I use it to record long, rambling brain dumps and feed them straight to the agent. | https://monologue.to |
| Impeccable | A design skill for when the UI actually matters. Fights the generic "AI slop" look. | https://impeccable.style |

## What Compound Engineering actually is

A group of very conscientious engineers sat down and encoded the whole process from idea to shipped, maintained product. The philosophy is 80 percent planning and review, 20 percent execution.

The result behaves like a talented, patient engineering team. Instead of prompting a model to "write code," you run a sequence of skills that brainstorm with you, write a plan, build it, review it from several angles, and record what was learned so the next run starts smarter. You get to be the world's laziest product manager.

The plugin has 36 skills. You need six.

## The loop

Run these in order, in your repo, inside Claude Code (or Codex, Cursor, etc.).

1. `/ce-brainstorm`: What does this need to be? Paste your rough brain dump. It reads the codebase and asks you one decision at a time until it has real requirements.
2. `/ce-plan`: What is needed to accomplish this? Turns the requirements into an implementation-ready plan. These plans are thorough and technical. If it is too dense, ask for a simpler, product-level explanation with a diagram. That is a normal and useful step.
3. `/ce-work`: Build it, with verification and commits.
4. `/ce-code-review`: A multi-persona review against the plan. Several reviewers with different concerns each give feedback; you choose which notes to take.
5. `/ce-commit-push-pr`: Commit, push, and open the pull request.
6. `/ce-compound`: Capture what was learned so the next loop starts smarter. This is the step that makes the whole thing compound: run one teaches it, run two remembers.

Also in the toolbox:

- `/ce-prototype`: Build a throwaway version so people can react to it before you commit. The decisions get written back into the plan.
- `/ce-debug`: Start from a bug, a screenshot, or a customer complaint. Finds the root cause with a causal chain and offers a fix and a PR.
- `/ce-babysit-pr`: Watches an open PR, handles review comments, fixes CI failures. It never merges on its own.
- `/lfg`: The whole pipeline, hands off: plan, build, simplify, review and apply fixes, browser tests, commit, push, open a PR, watch CI. It does not merge unless you tell it to. Always run `/ce-brainstorm` first so it plans against real requirements rather than a one-line prompt.

## A real example

This is the feature I built the morning of the talk.

The idea: demo pages for contractor sales calls that automatically reskin themselves based on the contractor's own website, so the demo looks like it was built for them rather than being generic.

The input was a rough voice memo, not a spec. Here is what happened:

1. I pasted the brain dump into Claude Code and ran `/ce-brainstorm`.
2. The agent read the notes, inspected the codebase, and asked follow-up questions to pin down what I actually wanted.
3. It wrote a detailed implementation plan. Too detailed for me to consume directly.
4. I asked for a simpler, more visual explanation of the plan at a product level. That version I could reason about.
5. I answered a handful of decision questions and told it to proceed.
6. It spent about 40 minutes building and testing the feature. Before it started, I told it not to come back until the work had been tested in the browser, checked visually, and brought to a high standard.

The point of the example is not the feature. It is that an ambiguous idea became implemented code with almost no manual handoff.

## How it learns over time

The most useful part of the workflow is that it builds its own internal wiki about how to work with me and inside the codebase: lessons from past tasks, preferred patterns, mistakes to avoid. Almost none of it is written by hand. It emerges from `/ce-compound` and from retrospectives, and only needs correcting when it drifts.

The practical result: even when the agent's context resets, the next run still knows the team's standards and my preferences.

## The lesson for PMs

AI makes PM quality visible.

The workflow exposes whether you understand the problem, whether you can articulate the strategy, and whether you can define success. Vague, incoherent, or incomplete instructions produce vague, incoherent, or incomplete code, immediately and in front of you.

Painful but valuable: a lot of the implementation failures PMs blame on engineering are actually caused by the PM's own instructions. This workflow does not make product thinking less important. It makes clear judgment and clear communication the whole job.

## Should PMs write production code?

Not always. When engineers are available, a PM writing production code is often not the highest-leverage use of time. But there are cases where it is clearly worth it:

- Turning a product idea into a real, interactive prototype inside the actual product.
- Skipping a long handoff cycle when a change is straightforward and well scoped.
- Producing a working PR instead of only a spec or a ticket.
- Shortening the wait between idea and experiment.

In a previous setup, tickets were auto-generated from meetings, reviewed quickly, and sent off to build automatically. That is how far the automation can go in the right environment.

## Getting started in 15 minutes

1. Install Claude Code (or Codex or Cursor) and open a repo you have permission to change.
2. Install Compound Engineering. In Claude Code:
   ```
   /plugin marketplace add EveryInc/compound-engineering-plugin
   /plugin install compound-engineering
   ```
   Then run `/ce-setup` once in the project.
3. Pick a small, real feature. Record a voice memo describing it the way you would explain it to a colleague. Dictate it with Monologue or type it.
4. Paste it in and run `/ce-brainstorm`. Answer the questions.
5. Run `/ce-plan`. If the plan is too technical, ask for a product-level summary.
6. Run `/ce-work`, then `/ce-code-review`, then `/ce-commit-push-pr`.
7. Run `/ce-compound`. Do it again tomorrow and notice what it remembered.

See `CHEATSHEET.md` for the full command list and install commands for other tools.
