# Phase 1 — Stats ingestion

**Guide:** §5 (all of it), §2 for WNBA-specific constraints
**Prerequisite:** phase 0

## Goal

Every WNBA player-game this season and prior seasons in `data/wnba.db`, plus who
was available but did not play, plus validation that proves it's correct.

## Build

**Source.** Pull box scores and play-by-play via sportsdataverse. If a needed
endpoint isn't exposed, call `stats.wnba.com` directly with `league_id='10'` and
browser-like request headers — without them it hangs rather than erroring, which
is confusing the first time. Do not build on Basketball Reference; it rate-limits
aggressively and is for cross-checking only.

**Raw first.** Every response goes to `data/raw/stats/` as JSON before parsing.

**Tables.** See guide §5.2 for full column lists.

- `games` — one row per game, including `overtime_periods` and estimated pace
- `player_games` — one row per player per game
- `availability` — **one row per player per game including players who did not
  play**, with a status reason (`played`, `dnp_coach`, `dnp_injury`, `dnp_rest`,
  `inactive`, `not_on_roster`). This is the table people forget. The minutes model
  in phase 5 needs to know who *could* have played.
- `players`, `teams` — reference tables

**Possessions.** Estimate as `FGA − OREB + TOV + 0.44 × FTA`. The 0.44 is an
NBA-derived approximation and is not exactly right for the WNBA. Use it, and
record in `DECISIONS.md` that it's an approximation with a note that it can be
derived properly from play-by-play later.

**Idempotency.** Track the last-ingested game date in the database. A second
`update` on the same day fetches nothing.

## Validation — build these, run them every ingest

Print each with the specific failing rows, not just pass/fail.

- Games per team match the published schedule (44 in 2026, 15 teams, 330 total)
- **Team minutes per game sum to 200, plus 25 per overtime period.** This single
  check catches an enormous share of parsing bugs. A game summing to 187 means a
  player was dropped.
- `2×(FGM − FG3M) + 3×FG3M + FTM = PTS`
- `REB = OREB + DREB`
- No player appears twice in one game
- No game date outside the season window
- Every `player_id` in `player_games` exists in `players`

## Expansion teams

Toronto Tempo and Portland Fire began play in 2026 and have no prior history.
Confirm the pipeline handles them without crashing and without silently imputing
something absurd. Phase 4 adds the proper fallback; here, just make sure ingestion
doesn't break.

## Definition of done

- `python run.py update` runs twice; second run reports 0 new games
- All validation checks pass, or the failures are explained with specific rows
- Summary printed: seasons, games, player-games, date range, checks passed
- `availability` contains rows with `minutes_played = 0`

## Stop

Print the summary and validation results. Update `PROGRESS.md` and `DECISIONS.md`.
Wait.
