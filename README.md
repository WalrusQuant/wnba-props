# WNBA Player Prop Model

A build path for a WNBA player prop projection model, designed to be built with a
coding agent by someone who has never shipped a project.

Repository: [github.com/WalrusQuant/wnba-props](https://github.com/WalrusQuant/wnba-props)

## Start here

```bash
git clone https://github.com/WalrusQuant/wnba-props.git
cd wnba-props
```

Open your coding agent in this directory and say:

> start following the build path

The agent reads `AGENTS.md`, checks `PROGRESS.md`, and builds one phase. Then it
stops and waits for you. Say "continue" for the next one.

**Do not tell it to do several phases at once.** The gates exist because you need
to read each phase's output before the next builds on it.

## What's here

| Path | What |
|---|---|
| `AGENTS.md` | Standing instructions the agent follows in every phase |
| `PROGRESS.md` | Which phase is current — the agent reads and updates this |
| `build/` | One spec per phase. The agent's instructions. |
| `docs/wnba-prop-model-guide.md` | **The reference.** Why every decision was made. Read this yourself. |
| `DECISIONS.md` | Log of choices made during the build |

## Before you start

1. Install [`uv`](https://astral.sh/uv), Git, and [DB Browser for SQLite](https://sqlitebrowser.org).
2. Read guide §0 through §4. Twenty minutes. It will save you weeks.
3. If you plan to collect odds data, sign up at **`the-odds-api.com`** (with
   hyphens — see guide §6.1) and put the key in `.env`. The free tier is enough
   to develop against.

## The one thing that can't wait

Odds data is ephemeral and cannot be back-filled. Stats history is always
re-fetchable; a price snapshot from last Tuesday is gone forever. Get phase 2
running early even if the model won't exist for two months.

## Expectations

Player props carry 6–12% hold. Beating that is hard, and the most likely outcome
is a well-built model that doesn't. That's a successful project — you'll come out
knowing distributional modeling, hierarchical shrinkage, Monte Carlo simulation,
and time-series validation.

The failure mode is a model that *appears* to win because it leaked. Most of the
rules in this repo exist to prevent that one outcome.
