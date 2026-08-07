# Progress

**Agent: read this first. Build the first phase not marked complete, then stop.**

Mark a phase complete only when its Definition of Done checks pass and the user
has seen the output.

| # | Phase | Spec | Status |
|---|---|---|---|
| 0 | Environment and scaffold | `build/00-setup.md` | ✅ complete |
| 1 | Stats ingestion | `build/01-stats-ingestion.md` | ✅ complete |
| 2 | Odds ingestion | `build/02-odds-ingestion.md` | 🟡 built, not live-verified (see phase log) |
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

### Phase 1 — Stats ingestion (2026-08-07)

**Source substitution (read this first):** this sandbox's network policy
blocks direct calls to `stats.wnba.com` and ESPN's API (confirmed 403 policy
denials, not something to retry around per the environment's own proxy
guidance). Built on `sportsdataverse-data`'s GitHub release assets instead —
the same pre-built parquet snapshots the real `sportsdataverse` package's WNBA
loaders read from, and the guide's ranked-first source. Fetched directly with
stdlib `urllib` + `pyarrow` rather than installing the `sportsdataverse`
package, to avoid pulling in its much heavier dependency tree
(xgboost/scikit-learn/pillow/xarray) for what amounts to three parquet
downloads. Full reasoning in `DECISIONS.md`.

**Built:** `src/config.py` (loads `config.yaml` once), `src/db.py` (SQLite
schema: `teams`, `players`, `games`, `player_games`, `availability`,
`scheduled_games`, `ingest_meta`), `src/sdv_fetch.py` (downloads one season's
parquet release asset, saves it as raw JSON under `data/raw/stats/` before
any parsing, returns parsed rows), `src/ingest_stats.py` (builds every table,
classifies DNP reasons into the status enum, estimates possessions/pace, runs
all validation, prints the summary — wired into `python run.py update`).
Added two dependencies: `pyarrow` (parquet parsing) and `pyyaml` (config
parsing) — justified in `DECISIONS.md`, no others.

**Idempotency:** historical seasons (everything before the current config
`season`) are marked backfilled in `ingest_meta` and skipped on later runs;
the current season is always re-fetched but only genuinely new rows change
the row counts. `last_ingested_game_date` is also tracked in `ingest_meta`
per the spec's literal wording.

**DoD checks:**
- `python run.py update` run twice: first run — `5885 new games, 126547 new
  player-games`; second run — `skipping 24 already-backfilled season(s)...
  0 new games`. Confirmed idempotent.
- All six of the spec's validation checks ran and printed specific failing
  rows where they didn't pass outright — not just pass/fail:
  - games per team vs. published schedule: **PASS-with-explained-deviation** —
    13 of 15 teams exactly 44, 3 teams (Dallas Wings, Las Vegas Aces, New York
    Liberty) at 45-46 from an extra Commissioner's Cup final game (real
    schedule fact, not a bug).
  - team minutes sum to 200 (+25/OT): **FAIL, 2528 of 11036 team-games**,
    essentially entirely confined to the 2002-2008 seasons (85-100% failure
    rate those years) where ESPN's archived box scores are missing some
    bench/garbage-time minutes — **0 failures for every season 2013-2026**,
    including all of 2026. Investigated and explained in `DECISIONS.md`
    rather than loosened to hide it.
  - points reconcile (2×(FGM−FG3M)+3×FG3M+FTM=PTS): **FAIL, 1 of 126,547
    rows** — a single 2015 game/player where ESPN's box score itself doesn't
    reconcile. Left as-is, not silently corrected; see `DECISIONS.md`.
  - rebounds reconcile (REB=OREB+DREB): **PASS**, all 106,001 rows.
  - no duplicate player-games: **PASS**.
  - no game date outside its season window: **PASS**, all 5,885 games.
  - every `player_id` in `player_games` exists in `players`: **PASS**, all
    126,547 rows.
  - (added, not in the spec's list, same "never silently drop a row" rule):
    367 of 5,885 completed games have zero `player_games` rows at all — a
    real source-coverage gap, 256 of them in the 2002 inaugural season alone,
    tapering to isolated one-offs through 2018 and none from 2019 on.
- Summary printed every run: seasons (2002-2026), games (5,885),
  player-games (126,547), players (1,037), teams (31 — 15 current franchises
  plus historical/relocated team IDs, e.g. the 2000-2002 Portland Fire is a
  different `team_id` than the 2026 expansion team of the same name), date
  range (2002-05-25 to 2026-08-01).
- `availability` DNP breakdown: played 114,593; dnp_coach 6,457; dnp_injury
  5,049; dnp_rest 71; inactive 377; not_on_roster 0 (deliberately unpopulated
  in this phase — see `DECISIONS.md`).
- Expansion teams: Toronto Tempo (28 games) and Portland Fire (29 games, its
  own `team_id` distinct from the historical 2002 franchise) both ingested
  cleanly — no crash, no absurd imputation.

**Unresolved / carried forward:**
- 2002-2008 team-minutes totals are lower-confidence (see above) — phase 4+
  should treat those seasons' minutes as less reliable, or exclude them, when
  building minutes features/priors.
- `not_on_roster` status is never populated (needs point-in-time roster/
  transaction data this phase doesn't ingest) — revisit if phase 5's minutes
  model needs that distinction.
- The single points-reconciliation anomaly (`game_id=400610830`,
  `player_id=2590050`) is unresolved by design — flagged, not corrected.
- `sportsdataverse-data`'s refresh cadence isn't verified to be same-day —
  worth checking before phase 10 automation relies on it for
  next-morning-after-games freshness.

### Phase 2 — Odds ingestion (2026-08-07) — built, NOT marked complete

**Read this before treating phase 2 as done: it isn't yet, and can't be from
here.** Two independent blockers, both explained in full in `DECISIONS.md`:

1. This sandbox's network policy blocks `api.the-odds-api.com` /
   `the-odds-api.com` outright (same 403 policy denial as `stats.wnba.com`
   in phase 1) — confirmed via the proxy's own status endpoint, not something
   to retry around.
2. No `ODDS_API_KEY` is set — signing up at `the-odds-api.com` (with hyphens)
   is a step only you can do.

Rather than fake a passing run, I built everything and verified every piece
that *can* be verified without a live call, and left the rest honestly
unverified. **Do not treat this as "phase 2 complete."**

**Built:** `src/odds_client.py` (The Odds API client: lists events, fetches
one event's player-prop odds, saves the raw response before parsing, never
lets the API key reach a log line or a saved file), `src/ingest_odds.py`
(orchestrates the run, classifies today's slate in US/Eastern time, parses
Over/Under pairs into rows, handles every error case the spec lists without
crashing, prints the snapshot summary and quota), `odds_snapshots` table
(never updated in place, one row per observed line, with a UNIQUE constraint
so re-parsing the same raw file is idempotent), `--dry-run` flag on
`python run.py update`, `tests/test_ingest_odds.py` (5 unit tests against a
synthetic fixture — added `pytest` as a dev dependency, justified in
`DECISIONS.md`). `config.yaml` gained an `odds:` section (sport key, markets,
regions, price format, snapshot cadence).

**What was actually verified, for real, in this environment:**
- No-key path: `python run.py update` with no `.env` prints a helpful
  message and skips odds ingestion cleanly; stats ingestion still runs.
- Network-failure path, genuinely triggered (not simulated): with a
  placeholder key, `python run.py update` hit the real proxy rejection of
  `api.the-odds-api.com`, logged one clean line naming only the endpoint
  path, and exited 0 — no traceback, and the key never appeared in any log
  file (grepped to confirm).
- Parser correctness: all 5 tests in `tests/test_ingest_odds.py` pass —
  Over/Under pairing into one row, alternate-market flagging, an
  unconfigured market at a book correctly dropped, an event with no
  bookmakers yielding zero rows (not an error), multiple books for the same
  player/market all kept.
- `--dry-run` end-to-end: placed one synthetic raw file (clearly fake,
  labeled, and deleted afterward), ran `--dry-run` twice — first run parsed
  and inserted 1 row into `odds_snapshots` with the raw file's original
  timestamp preserved; second run inserted 0 (idempotent, via the UNIQUE
  constraint). Cleaned up afterward: `data/raw/odds/` and `odds_snapshots`
  are both empty again in the committed state.

**Not verified (can't be, from here):** quota-header parsing
(`x-requests-remaining` etc.) against a real HTTP response, and the
credit-projection arithmetic against real quota numbers — the code follows
the API's documented header contract and was reviewed by inspection, but no
live response was ever reachable.

**To actually finish this phase,** one of:
- Run `python run.py update` yourself, somewhere without this sandbox's
  network restrictions, after copying `.env.example` to `.env` and adding
  your real `ODDS_API_KEY`; or
- Grant this environment network access to `the-odds-api.com` and I'll run
  it here.

Either way, once a real snapshot lands, I'll print the actual snapshot
summary and quota per the spec's "Stop" instruction, and only then mark this
row ✅ in the table above.
