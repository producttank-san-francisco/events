# Cheat Sheet

One page. The commands I use, what each one does, and how to install the plugin.

## Install Compound Engineering

Claude Code

```
/plugin marketplace add EveryInc/compound-engineering-plugin
/plugin install compound-engineering
```

Cursor (in Agent chat)

```
/add-plugin compound-engineering
```

Codex CLI

```
codex plugin marketplace add EveryInc/compound-engineering-plugin
codex plugin add compound-engineering@compound-engineering-plugin
```

In Codex, invoke skills with `$` instead of `/` (for example `$ce-plan`, `$lfg`).

After installing, run `/ce-setup` once in each project. Other editors (Cline, Copilot, OpenCode, and more) are covered in the plugin README: https://github.com/EveryInc/compound-engineering-plugin

## The loop (run in order)

| Command | What it does |
|---|---|
| `/ce-brainstorm` | Turns a rough idea into real requirements. Reads the codebase, asks you one decision at a time. Paste your brain dump here. |
| `/ce-plan` | Turns requirements into an implementation-ready plan. Ask for a simpler product-level explanation if it is too technical. |
| `/ce-work` | Builds the plan, with verification and commits. |
| `/ce-code-review` | Multi-persona review against the plan. You pick which notes to take. |
| `/ce-commit-push-pr` | Commit, push, open the PR. |
| `/ce-compound` | Writes down what was learned so the next run starts smarter. |

## Also in the toolbox

| Command | When |
|---|---|
| `/ce-ideate` | Before the loop, when you don't know what to build yet. |
| `/ce-prototype` | During the loop, to feel a thing before committing. Throwaway build; decisions written back into the plan. |
| `/ce-simplify-code` | After `/ce-work`, before review. Cleans up what was just written. |
| `/ce-debug` | Starting from a bug, a screenshot, or a customer complaint. Root cause, causal chain, optional fix and PR. |
| `/ce-babysit-pr` | After the PR is open. Watches it, handles review comments, fixes CI. Never merges on its own. |
| `/lfg` | The whole pipeline, hands off: plan, build, simplify, review and apply fixes, browser tests, commit, push, open PR, watch CI. Does not merge unless you tell it to. Run `/ce-brainstorm` first. |

## The rest of the stack

| Tool | Link |
|---|---|
| Claude Code | https://claude.ai/code |
| Compound Engineering guide | https://every.to/guides/compound-engineering |
| Monologue (voice to clean text) | https://monologue.to |
| Impeccable (design skill) | https://impeccable.style |

## Three habits that matter more than the tools

1. Brain dump out loud, then let `/ce-brainstorm` ask the questions. Don't try to write a perfect spec first.
2. When a plan is too technical, ask for a product-level version with a diagram. Reasoning about the plan is your job; reading every line is not.
3. Set the quality bar before the agent starts: tested in the browser, checked visually, done to a high standard. Then let it run.
