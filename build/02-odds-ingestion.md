# Phase 2 — Odds ingestion

**Guide:** §6 (all of it)
**Prerequisite:** phase 1

## Goal

A growing, timestamped archive of prop lines and prices that the user owns.

**Start this phase early even though the model doesn't exist yet.** The Odds API
offers historical odds, but coverage varies by plan, bookmaker, market, and time
period. It may not have the exact player-prop snapshot you need later, so build
your own timestamped archive for the markets and books you intend to model.

## Build

**Provider.** The Odds API at `the-odds-api.com`. Key in `.env` as
`ODDS_API_KEY`. Never print it, log it, or write it to a file.

Note for the user if it comes up: `theoddsapi.com` without hyphens is an
unaffiliated impersonator reselling their data. The official domain has hyphens.

**Endpoint.** WNBA player props are on the **event-odds endpoint**, queried one
game at a time — this affects credit math. Market keys are `player_points`,
`player_rebounds`, `player_assists`, and combinations. Alternate/milestone markets
use `_alternate` variants.

**Start with one market**, configurable in `config.yaml`, defaulting to
`player_points`. Debugging five markets at once while the join is broken is
miserable.

**Raw first.** `data/raw/odds/<ISO8601 timestamp>.json` before parsing.

**Table: `odds_snapshots`.** Store *every* snapshot; never update in place. This
is a time series and its value is in the movement.

```
snapshot_id, captured_at_utc, game_id, book, market,
player_name_raw, line, over_price, under_price, is_alternate
```

- `captured_at_utc` is the most important column in the database. Everything you
  can legitimately claim in phase 9 depends on knowing when a price existed.
- `player_name_raw` is the book's exact spelling, untouched. Name mapping happens
  in phase 3, into a *separate* column.
- A book may post several lines for the same player-market. Keep them all.

**Quota.** Read remaining quota from the response headers and print it after every
run. Also compute and print projected monthly usage at the current cadence, so the
user sees before automating whether they'll exhaust their plan.

**`--dry-run` flag.** Parses the most recent saved raw file instead of calling the
API. The user must be able to develop the parser without burning credits.

**Error handling.** None of these should crash the run — log and continue: no
games today, a game with no props posted, a book missing a market, an HTTP error,
a malformed response.

## Capture cadence

Configure snapshots at line open, midday, roughly an hour before tip, and **as
close to tip as possible**. That last one is the closing line — it's the yardstick
for everything in phase 9. If only one snapshot is affordable, make it that one.

## Definition of done

- A snapshot lands in `odds_snapshots` with a real UTC timestamp
- `--dry-run` re-parses without network access
- Remaining quota and projected monthly usage both printed
- Killing the network mid-run logs an error and exits cleanly

## Stop

Print the snapshot summary and quota. Update `PROGRESS.md`. Wait.
