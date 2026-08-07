# Progress

**Agent: read this first. Build the first phase not marked complete, then stop.**

Mark a phase complete only when its Definition of Done checks pass and the user
has seen the output.

| # | Phase | Spec | Status |
|---|---|---|---|
| 0 | Environment and scaffold | `build/00-setup.md` | ✅ complete |
| 1 | Stats ingestion | `build/01-stats-ingestion.md` | ⬜ not started |
| 2 | Odds ingestion | `build/02-odds-ingestion.md` | ⬜ not started |
| 3 | Cleaning and joining | `build/03-cleaning-joining.md` | ⬜ not started |
| 4 | Features | `build/04-features.md` | ⬜ not started |
| 5 | Minutes model | `build/05-minutes-model.md` | ⬜ not started |
| 6 | Rate models | `build/06-rate-models.md` | ⬜ not started |
| 7 | Simulation | `build/07-simulation.md` | ⬜ not started |
| 8 | Pricing | `build/08-pricing.md` | ⬜ not started |
| 9 | Evaluation | `build/09-evaluation.md` | ⬜ not started |
| 10 | Automation | `build/10-automation.md` | ⬜ not started |

Optional, run before phase 3 if applicable:

| — | Spreadsheet log audit | `build/03b-spreadsheet-audit.md` | ⬜ only if the user has a hand-kept prop log |

Something broken? See `build/recovery.md`.

---

## Phase log

Append one entry per completed phase: what was built, what the DoD checks
returned, and anything left unresolved.

<!-- Agent: append below this line. Do not rewrite earlier entries. -->

### Phase 0 — Environment and scaffold (2026-08-07)

Built with `uv init`: `pyproject.toml` (Python 3.11+, zero dependencies),
`run.py` (argparse entry point with the six subcommands, each stubbed to print
"not implemented — phase N builds this" and exit 0), `config.yaml` (just
`season: 2026`), and `src/log.py` (shared logging helper — console output plus
a timestamped file per run under `logs/`). Confirmed `.gitignore` and
`.env.example` were already correct from the repo scaffold.

DoD checks, all passing:
- `python run.py --help` lists all six subcommands — confirmed.
- `python run.py update` prints "not implemented — phase 1 builds this" and
  exits 0 — confirmed.
- `python run.py` with no arguments prints help and exits 0 — confirmed.
- `uv sync` works from a clean checkout — confirmed (tested by deleting
  `.venv` and re-running).

Nothing unresolved. No dependencies were added — see `DECISIONS.md`.

**To install `uv`:**
- macOS/Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

Then from the repo root: `uv sync` to create the virtual environment, and
`cp .env.example .env` (fill in `ODDS_API_KEY` when phase 2 needs it).

Command list:
```
python run.py update      fetch new games and odds since last run
python run.py clean       rebuild clean tables from raw
python run.py train       fit models, save to disk
python run.py project     today's slate -> console + CSV
python run.py evaluate    calibration and scoring on holdout
python run.py audit       data quality report
```
