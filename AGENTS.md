# Agent instructions

You are building a WNBA player prop projection model in this repository.

**Read `PROGRESS.md` before doing anything else.** It tells you which phase is
current. Do that phase only.

---

## Build protocol

This project is built in ten gated phases. The specs live in `build/`.

1. Read `PROGRESS.md`. Find the first phase not marked complete.
2. Read that phase's spec in `build/`.
3. Read the guide sections it references in `docs/wnba-prop-model-guide.md`.
   The spec tells you *what*; the guide tells you *why*, and the why contains
   constraints the spec assumes you know.
4. Build only that phase.
5. Run the phase's Definition of Done checks. Print the results.
6. Append any choices you made to `DECISIONS.md`.
7. Update `PROGRESS.md`: mark the phase complete, note anything unresolved.
8. **Stop and wait for the user.** Do not begin the next phase.

**The gate in step 8 is not a suggestion.** The user needs to read the output of
each phase before the next one builds on it. A model the user cannot debug is
worthless, and they cannot debug what they did not watch get built. If the user
says "do phases 4 through 7," build phase 4, stop, and tell them why.

If the user says "start" or "continue" with no phase named, that means: do the
current phase from `PROGRESS.md`.

---

## Standing rules

These apply in every phase. Do not restate them back to the user; just follow them.

**Environment**
- The user has never deployed anything. No Docker, no servers, no orchestration.
- Everything runs locally with one command until the user reaches phase 10.
- `uv` for dependencies. **Ask before adding any package and justify it.**
- Storage is a single SQLite file at `data/wnba.db`. No Postgres, no cloud DB.
- No notebooks, no web dashboard. Console output and CSV files.

**Data handling**
- **Write every raw API response to `data/raw/` as JSON before parsing it.**
  Parsers break; re-fetching is often impossible. Historical odds availability
  varies by provider, plan, bookmaker, market, and time period, so preserve
  the snapshots this project needs.
- Never silently drop a row. If something can't be matched or parsed, keep it
  with a null and a reason code, and report the count.
- Print before/after row counts at every transformation step.

**Correctness**
- **No leakage.** Features for game N use only data from games 1..N-1 plus
  pregame roster and injury info. Any scaler, imputer, or encoder is fit inside
  the training fold only. This is enforced by a test, not by discipline.
- **Time-based splits only.** Never a random train/test split.
- **WNBA games are 40 minutes.** A team plays 200 player-minutes per game, not
  240. Overtime adds 25. Do not use per-36 conventions anywhere — use per-40 or
  per-possession. Most basketball modeling material online is NBA-derived and
  will mislead you here.
- Every model outputs a distribution, never a point estimate.

**Operations**
- Every `run.py` subcommand is idempotent. Running twice does nothing the second
  time. A non-idempotent job that re-fetches nightly will get the user IP-banned.
- Commands fail helpfully. `project` before `train` prints "no trained model
  found, run `python run.py train` first" — not a traceback.
- Every tunable number lives in `config.yaml`. No magic numbers in code.
- Never print, log, or write an API key. It lives in `.env` only.

**Communication**
- Explain every new file in one sentence when you create it.
- Print readable summaries, not just success. Row counts, date ranges, match
  rates, distribution summaries. A phase that produces no readable output has
  produced no evidence it worked.
- **State failures plainly.** If the model loses to a baseline, say so and stop.
  Do not soften it, do not suggest the metric is unfair, do not proceed anyway.

---

## Layout

```
run.py              the only entry point the user types
config.yaml         every tunable number
.env                secrets, never committed
PROGRESS.md         phase state — read first, update last
DECISIONS.md        append-only log of choices and why
build/              phase specs — your instructions
docs/               the human-facing guide and rationale
src/                implementation
data/raw/           untouched API responses
data/wnba.db        SQLite, the source of truth
reports/            generated audits, calibration plots
tests/
```

## Command interface

```
python run.py update      fetch new games and odds since last run
python run.py clean       rebuild clean tables from raw
python run.py train       fit models, save to disk
python run.py project     today's slate -> console + CSV
python run.py evaluate    calibration and scoring on holdout
python run.py audit       data quality report
```

Build these subcommands as the phases that need them arrive. Do not stub all six
in phase 1.

---

## What not to build

Until phase 9 has demonstrated the model beats its baselines out of sample, do
not produce: bankroll curves, ROI figures, units-won, profit projections, or any
backtest against prices whose capture time is unknown. If the user asks for one,
say the sample size cannot support it and explain why. See guide §13.6.
