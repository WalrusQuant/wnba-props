# Decisions

Append-only. One entry per choice that could reasonably have gone another way.
Future-you and future-agent will not remember why, and the guide's defaults are
starting points, not conclusions.

Format:

```
## YYYY-MM-DD — <the choice>
**Decided:** what was chosen
**Alternatives:** what else was considered
**Why:** the reasoning
**Revisit if:** the condition that would change this
```

<!-- Agent: append new decisions below. Do not edit existing entries. -->

## 2026-08-07 — Phase 0 dependencies
**Decided:** `pyproject.toml` starts with zero dependencies. `run.py` uses only
the standard library (`argparse`, `logging`).
**Alternatives:** Add `pyyaml` now since `config.yaml` exists, and `python-dotenv`
since `.env.example` exists.
**Why:** Nothing in phase 0 parses `config.yaml` or reads `.env` yet — no
subcommand does real work. The spec says "no dependencies beyond what you need
for the CLI itself," and argparse needs nothing extra. Deferring these until
the phase that actually reads the file avoids an unused dependency and an
unasked-for addition.
**Revisit if:** Phase 1+ needs to parse `config.yaml` or load `ODDS_API_KEY` —
at that point, propose adding `pyyaml` / `python-dotenv` with justification
before adding them.

## 2026-08-07 — Logging destination
**Decided:** One shared helper (`src/log.py`) configures the root logger:
plain messages to the console, timestamped lines to a new file per run under
`logs/<UTC-timestamp>.log`.
**Alternatives:** A single rolling `logs/run.log` file; a logger per module.
**Why:** The spec asks for "one helper the whole project uses, not a logger
per module." A timestamped file per run keeps each `python run.py <cmd>`
invocation's output separable without needing log rotation logic yet.
**Revisit if:** Log volume across many runs makes `logs/` unwieldy — switch to
a single rotating file at that point.
