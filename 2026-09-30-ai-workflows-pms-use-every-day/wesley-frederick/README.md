# Wesley Frederick

ProductTank San Francisco organizer

**Talk:** Harness patterns (opening talk)

**Event:** [AI Workflows PMs Use Every Day](https://github.com/producttank-san-francisco/events/tree/main/2026-09-30-ai-workflows-pms-use-every-day) — September 30, 2026, at Cribl, San Francisco

## Links

- **Slides:** [Harness patterns deck](https://docs.google.com/presentation/d/14niptypjY01zG5GDteGOaYHUIYe-Qj0vf9GQB53jlgI/edit?usp=sharing) (Google Slides; anyone with the link can view)
- **Tool:** [jact](https://github.com/WesleyMFrederick/jact), a command-line tool that maps, checks, and pulls sections out of Markdown files, so an AI gets only the context it needs. ISC license.
- **Further reading:** [two articles, each with a plain-language overview](#further-reading)

## Summary

What sits underneath every AI tool, and how to judge an AI workflow by its design instead of its prompt.

This page covers the building blocks of a harness, a test that shows why the harness matters, four questions to ask about any AI workflow, and four habits for designing your own.

## The one-sentence version

> "The prompt is only the visible part. Below it is the harness — the software around the model that decides what the model sees, runs tools, and picks what happens next."

Ask about the workflow in addition to the prompt.

## Four questions for any AI workflow

1. What should the model see?
2. What should the model decide?
3. What should software guarantee?
4. Where should a human decide?

Don't only ask, "What prompt did they use?" Also ask, "What workflow did they design, and what would I change for mine?"

## What a harness actually is

The building blocks under every AI tool, from the "Underneath it all" slide:

- **Model call:** the one basic unit. The model could be a large model, a small one, or a small decision model. The pattern is the same.
- **Four things go into a call:**
  - **System prompt:** the standing instructions.
  - **Your message.**
  - **Tools available:** the list of tools the model may ask for.
  - **Injected context:** text the harness adds on its own, from hooks and from code inside the harness. You never see it.
- **Model response:** one thing comes out: text, or a tool request. A tool request is a request represented as data: which tool, with which inputs. It is not the action itself. The model doesn't run anything.
- **Harness:** builds each call and decides what happens next. It runs a tool, builds another call, or stops and answers. It feeds the results into the next call. The model never sees its own history unless the harness puts it back in.

Every feature you use is the harness making those choices, and every feature is a choice you could make differently.

## Same model, different harness, different result

Most of an AI product is the harness, not the model.

Composio test (Aug. 2026): one model, Kimi K3, ran 25 tasks in 8 harnesses.

| Harness | Solved | Time | Cost |
|---|---|---|---|
| oh-my-pi | 88% | 3.9 min | $10.93 |
| Kimi Code | 84% | 4.7 min | $12.87 |
| Claude Code | 76% | 5.5 min | $35.37 |

Judge any harness on three numbers: success, wall time, cost.

## Let the model judge; let software guarantee

> "Fuzzy questions go to the model. Exact questions go to code."

## Pack context like a carry-on, not a moving truck

Context is everything sent to the model on one call.

Send each step only what it needs: the article, the style guide, 3 related pages. Not the whole wiki and every tool. The model can't un-see what you send it.

## Think like a harness designer

Four habits, adapted from JD Forsythe's "10 Claude Code Principles":

1. **Route:** send each step only what it needs.
2. **Harden:** let code do what code can guarantee.
3. **Externalize:** keep plans and state in files, not the chat.
4. **Gate:** put a person at decisions that send, pay, or delete.

## Further reading

- **[HarnessTax: How Much Does the Harness Matter for Coding Agents?](https://harnesstax.github.io/)** — UC Berkeley and Arena Intelligence study of 7 models in 3 harnesses: the harness changed cost by up to 5x but barely changed success rate. [Read Article Overview](harnesstax-article-overview.md)
- **[Jev's Architecture Unmasked](https://archerhume.com/posts/jevs-architecture-unmasked)** — Archer Hume probes Jev with about 10,000 API calls and concludes it is a causal transformer (likely sparse MoE) that reads shared state once and returns trained probabilities directly instead of generating text. [Read Article Overview](jevs-architecture-unmasked-article-overview.md) · [Read Jev Architecture: Translated](jev-architecture-translated.md)
