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

## 2026-08-07 — Stats source: sportsdataverse-data release assets, not live stats.wnba.com/ESPN calls
**Decided:** `src/sdv_fetch.py` downloads season-level parquet snapshots directly
from `github.com/sportsdataverse/sportsdataverse-data/releases/download/...`
(the same GitHub release assets the real `sportsdataverse` Python package's
`load_wnba_*` loaders read from) via stdlib `urllib`, rather than calling
`stats.wnba.com` or ESPN's live API, and rather than installing the
`sportsdataverse` package itself.
**Alternatives:** (1) Call `stats.wnba.com` directly with `league_id='10'` and
browser headers, as the spec's fallback describes. (2) Install `sportsdataverse`
and call its `load_wnba_player_boxscore` / `load_wnba_team_boxscore` /
`load_wnba_schedule` functions directly.
**Why:** This sandbox's network policy blocks `stats.wnba.com` and ESPN's API
hosts outright (403 policy denial at the egress proxy — confirmed via
`/__agentproxy/status`, not something to retry or route around). GitHub
release-asset downloads (`github.com/.../releases/download/...`, which
redirect to `release-assets.githubusercontent.com`) are allowed. Reading the
`sportsdataverse` package's source showed its WNBA loaders fetch from exactly
these release URLs — the data is the same, ranked-first source the guide
recommends ("sportsdataverse... Start here"), just reached directly instead of
through the package. Installing the package itself would have pulled in
`xgboost`, `scikit-learn`, `pillow`, `xarray`, and more — far more weight than
three parquet downloads need, and `pyproject.toml` should stay light per the
standing rules. Parsing needs only `pyarrow` (added) to read the parquet
files; no `pandas`/`numpy` were added since plain Python loops and dicts are
fast enough at this row count (~127k player-games) and the project's later
phases can decide their own dataframe needs.
**Revisit if:** stats.wnba.com or ESPN's API become reachable from this
environment (e.g. a different network policy) and richer endpoints — hustle
stats, tracking data, shot charts, play-by-play beyond what sportsdataverse-data
publishes — are needed. Also revisit if sportsdataverse-data's refresh cadence
(not verified to be real-time; it's a periodically-refreshed mirror) proves too
stale for same-day `update` runs once phase 8/10 need current-day rosters.

## 2026-08-07 — Raw snapshot granularity: one JSON file per season per dataset
**Decided:** The "raw-then-parse" rule is satisfied at the season level:
`data/raw/stats/{schedule,player_box,team_box}_{season}.json`, written
immediately after downloading and before any transformation, one file per
season per dataset (75 files for the full 2002-2026 backfill, ~226MB).
**Alternatives:** Save the literal parquet bytes as fetched (true wire
format, but not human-greppable). Save one file per game (true "one API
response" granularity, but the source here is pre-aggregated season files,
not per-game API calls).
**Why:** The source is itself a season-granular pre-aggregated snapshot, not
a per-game live API — there is no finer-grained "raw response" to preserve.
JSON keeps the raw layer greppable and re-parseable without a parquet reader,
matching the intent of the rule (fix the parser, not re-fetch) even though
the wire format was parquet, not JSON.
**Revisit if:** A future phase needs today's slate before sportsdataverse-data
refreshes (see above) and switches to a live per-game source — then raw files
should move to per-game/per-request granularity.

## 2026-08-07 — Historical backfill window: full 2002-2026 history
**Decided:** `config.yaml`'s `stats.history_start_season: 2002` backfills every
season sportsdataverse-data publishes, not just recent years. Historical
seasons are marked backfilled in `ingest_meta` and skipped on later `update`
runs; only the current season is re-fetched each time.
**Alternatives:** A shorter recent window (e.g. 2021-2026, matching the WNBA's
last few rule-set eras).
**Why:** The fetch is cheap (~50s network + parse time for all 25 seasons) and
SQLite handles ~127k player-game rows trivially, so there's no real cost to
keeping the full history on disk. Deciding how much of it is *relevant* — the
guide is explicit that the 2025-26 CBA's roster-size change means pre-2026
minutes priors don't transfer cleanly, though rate priors transfer better — is
a modeling-phase (5/6) concern about which seasons to weight, not an
ingestion-phase concern about which seasons to store.
**Revisit if:** Ingestion time becomes a problem, or phase 5/6 conclude very
old seasons (pre-2013 play style, pre-3-team-expansion) add noise rather than
signal to the priors and should be excluded at the query level.

## 2026-08-07 — Possession estimate coefficient
**Decided:** `POSS = FGA - OREB + total_TOV + 0.44 * FTA`, using the box
score's `total_turnovers` field (player turnovers + team-attributed
turnovers like shot-clock violations, which also end a possession) rather
than just player turnovers. `0.44` is stored in `config.yaml` as
`stats.possession_fta_coefficient`.
**Alternatives:** Derive the true FTA-ends-possession fraction from
play-by-play, which this phase doesn't ingest.
**Why:** Exactly the spec's formula. `0.44` is an NBA-derived approximation,
not verified for the WNBA. Recorded here per the spec's explicit instruction.
**Revisit if:** Play-by-play is ingested later (phase 7's simulation may want
it anyway) — derive the real WNBA coefficient by counting actual possession
endings, per guide §5.3.

## 2026-08-07 — DNP reason -> availability status classification
**Decided:** `classify_status()` in `src/ingest_stats.py` maps ESPN's raw
free-text `reason` field to the fixed six-way status enum by exact-match
lookup tables: `{"COACH'S DECISION", "DID NOT DRESS"} -> dnp_coach`,
`{"REST", "RETURN TO COMPETITION RECONDITIONING"} -> dnp_rest`,
`{"NOT WITH TEAM", "PERSONAL", "SUSPENDED BY LEAGUE"} -> inactive`, and
everything else (body-part names, "INJURY", "ILLNESS", "CONCUSSION",
"SURGERY", "STRAIN", "SORENESS", "SPRAIN", etc. — about 65 distinct raw
strings) defaults to `dnp_injury`. The raw text itself is preserved
unclassified in `player_games.dnp_reason`, so nothing is lost if this mapping
needs revisiting.
**Alternatives:** Keyword/regex matching on the injury-adjacent bucket
instead of defaulting everything unrecognized to `dnp_injury`.
**Why:** Inspected the actual distribution of `reason` values across the full
2002-2026 history first (about 12,000 DNP rows) rather than guessing; the
non-injury/rest/coach categories are a short, stable, enumerable list, so
exact-match is more precise than keyword matching and the default-to-injury
fallback is safe because it's the largest and most heterogeneous real
category anyway.
**Revisit if:** A new raw reason string starts appearing that clearly isn't
an injury (spot-check `dnp_reason` distribution periodically) — add it to the
appropriate exact-match set.

## 2026-08-07 — `not_on_roster` status is not populated in phase 1
**Decided:** The `availability.status` enum includes `not_on_roster` per the
spec, but no rows use it yet (0 of ~126k rows) — every row this phase builds
comes from ESPN's per-game box score, which only lists players who were
either in the game or explicitly marked DNP with a reason. It does not list
players who weren't part of that game's roster at all (e.g. two-way/inactive
players not on the active gameday roster).
**Alternatives:** Diff each team's full season roster (`load_wnba_rosters`-
equivalent) against each game's box score roster to infer `not_on_roster` for
players who were on the team but absent from a specific game's listing.
**Why:** Season-level rosters aren't point-in-time — a player could join or
leave a team mid-season, and diffing a season roster against an early-season
game would wrongly mark a not-yet-signed player as "not on roster" for that
game instead of correctly having no row at all. Getting this right needs
transaction dates this phase doesn't ingest. Reporting 0 rows honestly (with
an explanation printed in the ingest summary) is preferable to guessing.
**Revisit if:** Phase 5's minutes model needs to distinguish "not on the
active roster" from "simply absent from the data" — at that point, ingest
transaction/roster-change dates to do this correctly.

## 2026-08-07 — Team-minutes validation tolerance and a real historical data-quality finding
**Decided:** The team-minutes-per-game check (`stats.team_minutes_tolerance:
5` in config.yaml) flags a team-game only if summed player minutes deviate
from `200 + 25*OT` by more than 5 minutes, not on any nonzero deviation.
**Alternatives:** Exact-match check (flag any deviation from expected at
all).
**Why:** Investigated the actual deviation distribution before choosing a
tolerance instead of guessing: for 2013-2026 (6,450 team-games, including all
of the current 2026 season), the deviation is **exactly 0 for every single
team-game** — no tolerance needed there at all. For 2002-2008 (2,528 of 2,798
team-games, 85-100% per season), ESPN's archived box scores are missing
minutes for some bench/garbage-time players, a known gap in that era's
coverage, not a parsing bug in this pipeline — confirmed by checking that the
gap disappears completely and abruptly starting exactly at the 2013 season
boundary, which lines up with ESPN's switch to its modern event-ID/data
scheme. A small tolerance for 2009-2012 (13 team-games, <1% each season)
absorbs ordinary single-minute rounding noise. The check still prints every
specific failing game/team/diff per the spec's requirement, rather than
hiding the count.
**Revisit if:** Phase 4+ needs reliable minutes totals from 2002-2008 --
those seasons' player-level minutes should be treated as lower-confidence or
excluded rather than trusted at face value.

## 2026-08-07 — Points-reconciliation failure: one real anomalous row, left as-is
**Decided:** One player-game (`game_id=400610830`, `player_id=2590050`, Ally
Malott, 2015-09-11) fails `2*(FGM-FG3M)+3*FG3M+FTM == PTS`: makes reconcile to
10 points, ESPN's box score records 12. This row is kept in `player_games`
unmodified — no value was invented to force reconciliation.
**Alternatives:** Silently correct `points` to the computed value.
**Why:** The standing rule is "never silently drop a row... keep it with a
null and a reason code, and report the count" — the same principle applies to
silently *editing* a row to make a check pass. This is a single isolated
anomaly (1 of 126,547 rows) most likely an ESPN scorekeeping/archival error
from a decade-old game; the validation check did its job by catching and
printing it specifically, which is the point of running it.
**Revisit if:** More such anomalies turn up as data accumulates — worth
building a small `data_quality_flags` table if the count grows past a
handful, instead of only surfacing them in each `update`'s printed output.

## 2026-08-07 — Exhibition games (WNBA All-Star draft teams) excluded from every table
**Decided:** Schedule rows where either team's `display_name` starts with
`"TEAM "` (ESPN's naming convention for WNBA All-Star draft squads, e.g.
"TEAM COOP", "TEAM SPOON" in 2026) are excluded from `teams`, `games`,
`scheduled_games`, `player_games`, and `availability` entirely.
**Why:** These aren't real franchises — including them would corrupt the
15-team schedule-integrity check and add noise with no modeling value (an
All-Star exhibition isn't informative about a player's role on their actual
team). Filtering on the naming convention is more robust than an ID
allowlist, since it doesn't need updating each year as draft team names
change.
**Revisit if:** A real WNBA team is ever named starting with "TEAM " (very
unlikely) — switch to an explicit 15/16/17-team ID allowlist instead.

## 2026-08-07 — Added a validation check not in the spec's list: games with zero player_games rows
**Decided:** `_check_games_missing_player_data()` in `src/ingest_stats.py`
flags any completed game that has a `games` row but no `player_games` rows at
all — 367 of 5,885 games, 256 of them in 2002 alone, tapering to single
isolated games scattered through 2010-2018, and zero from 2019 onward.
**Why:** Not one of the spec's six listed checks, but the standing rule
"never silently drop a row... report the count" applies here too — a game
with no box score at all would otherwise pass every other check trivially
(there are no player rows to fail reconciliation) and disappear silently.
Checked whether this was a bug in my ingestion (e.g. dropping rows during
insert) versus genuinely absent from the source: the affected `game_id`s have
zero rows in the fetched `player_box` payload itself, before any of my code
runs — so it's a real source-coverage gap, concentrated almost entirely in
the WNBA's inaugural 2002 season, not a parsing defect.
**Revisit if:** A phase 4+ feature needs guaranteed box-score coverage for a
specific season — filter these game_ids out explicitly rather than relying on
their absence from `player_games` to do it implicitly.
