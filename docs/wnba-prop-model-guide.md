# Building a WNBA Player Prop Model

### A step-by-step plan for someone starting from zero, using a coding agent

---

## Contents

**Orientation**
- [0. Read this first](#0-read-this-first)
- [1. What you are actually building](#1-what-you-are-actually-building)
- [2. WNBA-specific things that will break an NBA-shaped model](#2-wnba-specific-things-that-will-break-an-nba-shaped-model)
- [3. Prerequisites and environment](#3-prerequisites-and-environment)
- [4. Project structure](#4-project-structure)

**Build phases**
- [5. Phase 1 — Stats data](#5-phase-1--stats-data)
- [6. Phase 2 — Odds data](#6-phase-2--odds-data)
- [7. Phase 3 — Cleaning, joining, and validation](#7-phase-3--cleaning-joining-and-validation)
- [8. Phase 4 — Features](#8-phase-4--features)
- [9. Phase 5 — The minutes model](#9-phase-5--the-minutes-model)
- [10. Phase 6 — Rate models](#10-phase-6--rate-models)
- [11. Phase 7 — Simulation](#11-phase-7--simulation)
- [12. Phase 8 — Pricing: de-vigging, edge, and sizing](#12-phase-8--pricing-de-vigging-edge-and-sizing)
- [13. Phase 9 — Evaluation and calibration](#13-phase-9--evaluation-and-calibration)
- [14. Phase 10 — Hosting and automation](#14-phase-10--hosting-and-automation)

**Reference**
- [15. Operating it](#15-operating-it)
- [16. Failure modes: the catalog](#16-failure-modes-the-catalog)
- [17. What this costs](#17-what-this-costs)
- [18. Sequencing: the honest version](#18-sequencing-the-honest-version)
- [19. Glossary](#19-glossary)
- [20. One last thing](#20-one-last-thing)

This guide is the **reference**: it explains why each decision was made. The
agent-facing specs live in `build/`, one file per phase — those tell the agent
*what* to build, this tells you *why*. Each `build/` file points back to the
sections here that it assumes you've read.

---

## 0. Read this first

**Who this is for.** You want to build a model that projects WNBA player statistics
(points, rebounds, assists, threes) and compares those projections to sportsbook
prop lines. You can read code but you have never shipped a project. You plan to do
the work with a coding agent — Claude Code, Codex, Cursor, or similar.

**What this document is.** A build order. Each phase has a goal, a set of decisions
already made for you, the specific things that go wrong, and a prompt you can hand
to your agent. Work the phases in order. Do not skip ahead to the modeling because
it's the fun part — the projects that fail, fail in phases 1 through 3.

**How to work with a coding agent on this.**

The agent will happily build all ten phases in one shot. Do not let it. A model you
cannot debug is worthless, and you cannot debug what you did not watch get built.

- One phase per session. End each phase with a command you run yourself that prints
  something you can read.
- Make the agent print intermediate output constantly. Row counts, date ranges, join
  failure counts, distribution summaries. If a phase produces no readable output, it
  produced no evidence it worked.
- When the agent proposes a library you have not heard of, ask why, and ask what it
  would do without it.
- Keep a `DECISIONS.md` file. Every time you settle a question — which data source,
  which distribution, which cutoff date — write one line about what you chose and
  why. In three weeks you will not remember, and neither will the agent.
- The agent's default failure mode is confident completion. It will write a
  backtest that returns 63% ROI and it will be wrong, because it leaked. Your job
  in this project is to be the person who does not believe the output.

**A note on expectations.** Sportsbooks price props with more data, better data, and
professional modelers. Player props specifically carry 6–12% hold, which is far
worse than sides and totals. Beating that is hard. Build this because modeling is
interesting and you'll learn a lot; treat any edge you find as a hypothesis to test,
not a paycheck.

---

## 1. What you are actually building

Strip away the betting framing. The core object is:

> For a given player in a given game, a **probability distribution** over how many
> points (or rebounds, or threes) they will record.

Not a number. A distribution. This is the single most important framing decision in
the project, and most beginner models get it wrong by projecting "Sabrina will score
19.4" and comparing that to a line of 18.5.

That comparison is meaningless. A player projected at 19.4 with a tight distribution
and a player projected at 19.4 with a wide one imply very different probabilities of
going over 18.5. The line is not asking "how many points?" — it's asking "what is
P(points ≥ 19)?" You need the whole curve to answer that.

Once you have the distribution, everything else is mechanical:

```
distribution  →  P(over)  →  compare to de-vigged market probability  →  edge
```

**The decomposition.** Nearly every counting stat factors the same way:

```
stat  =  playing time  ×  rate per unit of playing time
```

This matters because those two pieces have completely different behavior, different
data requirements, and different sources of error. Playing time is driven by rotation
decisions, injuries, foul trouble, and game script. Rate is driven by player skill,
role, and matchup. Mixing them into one model destroys your ability to reason about
either.

Roughly speaking, for a mid-season prop, uncertainty in playing time contributes more
error than uncertainty in rate. **Most of your modeling effort belongs in the minutes
model.** Beginners spend 90% of their time on shooting rates and 10% on minutes, and
that's backwards.

**What you'll build, end to end:**

| Layer | Produces |
|---|---|
| Stats ingestion | Historical box scores, play-by-play, rosters |
| Odds ingestion | Prop lines and prices, archived over time |
| Cleaning + joining | One trustworthy table linking props to outcomes |
| Features | Pace, rest, opponent, teammate availability, role |
| Minutes model | Distribution over minutes per active player |
| Rate models | Distribution over per-minute production |
| Simulation | Joint distribution over all stats for all players in a game |
| Pricing | De-vigged market probability, model edge, stake size |
| Evaluation | Calibration, CRPS, baseline comparison, CLV |
| Automation | It runs every morning without you |

---

## 2. WNBA-specific things that will break an NBA-shaped model

Almost everything written about basketball modeling online is about the NBA. If you
or your agent port those assumptions directly, you will get subtly wrong answers.
These are the differences that actually bite.

**Games are 40 minutes, not 48.** Four 10-minute quarters. This means a team plays
**200 player-minutes per game**, not 240. Overtime periods are 5 minutes, adding 25
team-minutes each.

Consequence: the standard "per-36 minutes" normalization is an NBA convention, and in
a 40-minute game it's an awkward one. A WNBA starter playing 34 minutes is playing
85% of the game, where an NBA player at 34 minutes is playing 71%. Use **per-40** or,
better, **per-possession** rates. If your agent writes `per_36` anywhere, ask it why.

**The season is short.** 44 games per team in 2026, up from 40 in prior years. Fifteen
teams, 330 total games. A full season of WNBA data is roughly what the NBA produces in
three weeks. Every statistical technique you use has to be chosen with this in mind —
this is a small-sample problem wearing a big-data costume.

**Rosters are small and minutes are concentrated.** Starters play a large share of
available minutes and the bench is short. One starter sitting reallocates minutes to
a small number of specific teammates, not diffusely across a 15-man rotation. This
makes teammate-availability features unusually powerful — and makes stale injury
information unusually costly.

**Roster rules changed under the new CBA.** The collective bargaining agreement
signed in the 2025–26 offseason increased roster sizes. Minutes distributions from
prior seasons therefore do not transfer cleanly. Do not blend pre-2026 minutes priors
into a 2026 minutes model without adjusting for this. Rate priors transfer better than
minutes priors.

**Two expansion teams have no history.** The Toronto Tempo and Portland Fire began
play in 2026. Their players have prior history from other teams, but the teams
themselves have no pace, no defensive profile, no rotation pattern. This is a
cold-start problem: your model needs an explicit fallback (league-average priors,
heavily shrunk) rather than silently producing garbage or crashing on a missing key.

**There is a mid-season break.** The 2026 season runs May 8 to September 24 with a
two-week break in early September for the FIBA Women's World Cup. Players participate
internationally during it. Treat the break as a discontinuity: rest features computed
naively across it will read "18 days rest," and form features will span a period
where players were doing something else entirely.

**Overseas play.** Many WNBA players compete in overseas leagues in the offseason.
Season-over-season carryover of conditioning and form is messier than in the NBA, and
some players arrive late or manage load.

**Markets are thinner.** Fewer books post WNBA props, they often post them later, and
limits can be lower than NBA markets. That does not prove they are inefficient. It
does mean sparse, stale, wide, and occasionally erroneous lines can make a backtest
look brilliant while being unavailable or unbettable at any meaningful size.

---

## 3. Prerequisites and environment

Do this before you open your agent. It takes twenty minutes and prevents a category
of problem that will otherwise waste days.

### 3.1 Install the basics

| Tool | Why | Get it |
|---|---|---|
| Python 3.11+ | Everything | python.org, or via `uv` below |
| `uv` | Package + environment manager. Fast, one tool, no venv confusion | astral.sh/uv |
| Git | Version control. Non-negotiable | git-scm.com |
| DB Browser for SQLite | Click around your database without writing SQL | sqlitebrowser.org |
| A GitHub account | Backup, and free automation later | github.com |

**Why `uv` and not pip/conda/poetry:** one binary, handles Python versions and
packages, and the failure modes are legible. When your agent says "install X," the
command is `uv add X` and it goes in `pyproject.toml` where you can see it.

### 3.2 Set the ground rules with your agent

Paste this at the start of every session:

```
Context for this project:
- I have never deployed anything. No Docker, no servers, no Kubernetes.
- Everything runs on my laptop with one command until I explicitly say otherwise.
- Use uv for dependencies. Ask before adding any package and justify it.
- Storage is a single SQLite file. No Postgres, no cloud database.
- No notebooks, no web dashboard. Console output and CSV files.
- Explain every new file in one sentence when you create it.
- End each phase with a command I can run that prints something readable.
  Then stop and wait for me.
```

### 3.3 Version control from minute one

```bash
git init
git add -A
git commit -m "start"
```

Commit at the end of every phase. When the agent breaks something in phase 6, you
want to be able to see exactly what changed since phase 5.

**Add a `.gitignore` immediately** containing at minimum:

```
.env
data/raw/
*.db
__pycache__/
.venv/
```

Two things must never be committed: your API keys, and large raw data files. But see
§10.4 — there's a nuance about the database that comes up when you automate.

### 3.4 Secrets

Create a `.env` file in the project root:

```
ODDS_API_KEY=your_key_here
```

Load it with `python-dotenv`. Never paste an API key into a source file, never paste
one into a chat with your agent, and never commit `.env`. If you do commit one by
accident, rotate the key — deleting the file does not remove it from git history.

---

## 4. Project structure

Decide this now so the agent doesn't invent a new layout every session.

```
wnba-props/
├── run.py                  # the only entry point you ever type
├── pyproject.toml
├── config.yaml             # every tunable number lives here
├── .env                    # secrets, never committed
├── README.md               # how to run it, written for future-you
├── DECISIONS.md            # a log of choices and why
├── data/
│   ├── raw/                # untouched API responses, JSON, by date
│   ├── wnba.db             # SQLite: the single source of truth
│   └── external/           # anything you tracked by hand
├── src/
│   ├── ingest_stats.py
│   ├── ingest_odds.py
│   ├── clean.py
│   ├── features.py
│   ├── model_minutes.py
│   ├── model_rates.py
│   ├── simulate.py
│   ├── price.py
│   └── evaluate.py
├── reports/                # audit reports, calibration plots, generated
├── logs/
└── tests/
```

### 4.1 The command interface

One entry point, subcommands, all idempotent:

```
python run.py update      # fetch new games and odds since last run
python run.py clean       # rebuild the clean tables from raw
python run.py train       # fit models, save to disk
python run.py project     # today's slate → console + CSV
python run.py evaluate    # calibration and scoring on holdout
python run.py audit       # data quality report
```

**Idempotent** means running a command twice does the same thing as running it once.
`update` on a day with no new games should print "0 new games" and exit, not
re-download the season. This matters enormously once you automate — a stuck loop that
re-fetches everything nightly is how you get IP-banned.

Every command should also fail helpfully. If you run `project` before `train`, it
should print "no trained model found, run `python run.py train` first" — not a
`FileNotFoundError` traceback.

### 4.2 The raw-then-parse rule

**Write every API response to `data/raw/` as JSON before you parse it.**

This is the single most valuable habit in a data project. Parsers break constantly —
a field gets renamed, a null appears where you expected a number, a player has an
apostrophe in their name. When that happens you want to fix the parser and re-run
against data you already have on disk. If you didn't save the raw response, your only
option is to re-fetch, and the exact data may not be available on your provider's
historical endpoint. Historical odds coverage varies by plan, bookmaker, market, and
time period, so save the snapshots this project relies on.

Name files so they're greppable: `data/raw/odds/2026-08-06T14-30-00Z.json`.

---

## 5. Phase 1 — Stats data

**Goal:** a local database containing every WNBA player-game this season and prior
seasons, plus who was and wasn't available for each game.

### 5.1 Sources, ranked

| Source | What it gives you | Cost | Verdict |
|---|---|---|---|
| **sportsdataverse / `wehoop`** | Play-by-play and box scores back to 2002, wraps ESPN and stats.wnba.com, with pre-built cached loaders | Free | **Start here.** Pulls full history in seconds. |
| **stats.wnba.com direct** | Tracking data, hustle stats, lineups, shot charts — the deep stuff | Free | Use for anything the wrapper doesn't expose. |
| **`nba_api` package** | Same endpoints, Python-native | Free | Most endpoints accept `league_id='10'` for the WNBA. Handy if you already know it. |
| **Basketball Reference (WNBA)** | Clean season tables, good for sanity checks | Free | Rate-limits aggressively. Fine for cross-checking, terrible as a pipeline. |
| **Her Hoop Stats** | Advanced WNBA-specific metrics | Subscription | `wehoop` has functions for it if you have a login. Optional. |
| **Rotowire / beat reporters** | Confirmed lineups, injury news, minutes restrictions | Free to cheap | Not a database, but this is where the actual edge lives. See §5.5. |

`wehoop` is an R package; the Python side of sportsdataverse covers similar ground.
If you're working in Python and hit a gap, calling stats.wnba.com directly is
straightforward — it mirrors the stats.nba.com endpoint structure and requires the
same browser-like request headers (a `User-Agent`, `Referer`, and a few others) or it
will hang rather than error, which is confusing the first time.

### 5.2 Tables to build

**`player_games`** — one row per player per game:

```
game_id, game_date, player_id, player_name, team_id, opponent_id,
home_away, minutes, fga, fgm, fg3a, fg3m, fta, ftm,
points, oreb, dreb, reb, ast, stl, blk, tov, pf,
plus_minus, started, dnp_reason
```

**`games`** — one row per game:

```
game_id, game_date, season, home_team_id, away_team_id,
home_score, away_score, overtime_periods, possessions_est,
pace, home_off_rating, away_off_rating, attendance
```

**`availability`** — one row per player per game, **including players who did not
play**. This is the table people forget, and it is essential. Your minutes model
needs to know who *could* have played, not just who did.

```
game_id, player_id, status, minutes_played
```
where status is one of `played`, `dnp_coach`, `dnp_injury`, `dnp_rest`, `inactive`,
`not_on_roster`.

**`teams`** and **`players`** — reference tables with IDs, names, and every alias you
encounter. See §7.2 on why this matters more than it looks.

### 5.3 Possession estimation

Pace drives everything downstream. Estimate possessions per team per game:

```
POSS ≈ FGA − OREB + TOV + 0.44 × FTA
```

The 0.44 coefficient is an NBA-derived approximation of what fraction of free throw
attempts end a possession. It is approximately right for the WNBA but not exactly.
If you want to be rigorous, derive it from play-by-play by counting actual possession
endings. This is a good early exercise because it forces you to actually parse the
PBP data, which you'll need later anyway.

Pace = possessions per 40 minutes, adjusted for overtime.

### 5.4 Validation as you ingest

Do not trust a row count. Have the agent write checks that run every time:

- Games ingested per team per season matches the published schedule (44 in 2026).
- Team minutes per game sum to 200, or 200 + 25×OT periods. **This check catches an
  enormous number of parsing bugs.** If a game sums to 187, you dropped a player.
- Points per player reconcile: `2×(FGM − FG3M) + 3×FG3M + FTM = PTS`.
- `REB = OREB + DREB`.
- No player appears twice in the same game.
- No game date falls outside the season window.
- Every `player_id` in `player_games` exists in `players`.

Any check that fails should print the specific game and player, not just "validation
failed."

### 5.5 Availability and injury data — the hard part

Historical box scores are easy. Knowing **at projection time** who is playing tonight
is hard, and it's most of the value.

Injury reports come out shortly before tip. Confirmed starting lineups come out
closer still. A model that runs at 9 AM and a model that runs 30 minutes before tip
are different models, and the second one is far better.

Practical approach for a beginner:

1. **Phase 1:** ignore this. Build everything on historical availability (who
   actually played) so you can develop and evaluate the model. Accept that your
   backtest is optimistic because it knows who played.
2. **Phase 2:** add a manual override. A `today_out.csv` you edit by hand before
   running `project`. Ugly, works, takes two minutes a day.
3. **Phase 3:** automate scraping of an injury feed. Only after the model works.

Be explicit in your evaluation about which of these you used, because the difference
in measured performance between "knew the lineup" and "didn't" is large, and it is
the difference between a real result and a fantasy.

### 5.6 Agent prompt for phase 1

```
Build the stats ingestion layer for a WNBA player prop model.

- Pull WNBA box scores and play-by-play via sportsdataverse. If a needed endpoint
  is missing, call stats.wnba.com directly with league_id='10' and browser headers.
- Save every raw API response to data/raw/stats/ as JSON before parsing.
- Build tables in data/wnba.db: games, player_games, availability, players, teams.
- availability must include players who did NOT play, with a status reason.
- Estimate possessions per team-game and pace per game. Note in DECISIONS.md which
  coefficient you used for FTA and that it is an NBA-derived approximation.
- Write validation checks that run on every ingest:
    games per team match the published 44-game schedule
    team minutes per game sum to 200 (+25 per overtime period)
    points reconcile from FGM/FG3M/FTM
    rebounds reconcile from OREB/DREB
    no duplicate player-games
  Print each check's result with specific failing rows, not just pass/fail.
- Make `python run.py update` idempotent: running twice fetches nothing the second
  time. Track the last-ingested game date in the database.
- Print a summary: seasons loaded, games, player-games, date range, checks passed.

Stop when I can run `python run.py update` twice and see a clean report both times.
```

---

## 6. Phase 2 — Odds data

**Goal:** a growing archive of prop lines and prices, timestamped, that you own.

This is the part that may cost money and should be started early. The Odds API has
historical odds, but coverage varies by plan, bookmaker, market, and time period.
Collect the exact snapshots you need from day one rather than assuming they can be
retrieved later.

### 6.1 The provider

**The Odds API — `the-odds-api.com`** (with hyphens) is the standard choice for a
project this size. Around $30/month gets you 20,000 credits, all sports, all
bookmakers, all betting markets including player props, and access to historical
odds. There's a free tier at 500 credits/month with no historical access, which is
useful only for a small integration smoke test. It is not enough for real
player-prop development or daily collection; budget for paid access or choose
another data source. They also publish Excel and Google Sheets add-ons if you want
to poke at the data outside of code, and sportsdataverse maintains an R wrapper
(`oddsapiR`) for it.

**Check the domain carefully.** The Odds API has published a warning that
`theoddsapi.com` — the same name without hyphens — is an unaffiliated impersonator
reselling their data, registered in 2024 versus the real site's 2017. The official
domain is **`the-odds-api.com`**. Pricing and feature information from the wrong site
will not match what you actually get.

Alternatives exist at both ends: OpticOdds and Sportradar for professional-grade
feeds at professional prices, and a handful of newer low-cost vendors with free
tiers. If you try a smaller vendor, verify WNBA prop coverage and archive depth
yourself before depending on it.

### 6.2 Which markets to pull

WNBA player props live on the **event-odds endpoint**, not the main odds endpoint —
you query them one game at a time, which affects your credit math. Market keys look
like `player_points`, `player_rebounds`, `player_assists`, and combinations. Milestone
or "X+" style markets typically use `_alternate` variants of the same keys.

Start with **one market**: `player_points` or three-pointers made. Adding markets is
easy later; debugging five markets at once when your join is broken is not.

### 6.3 Credit budgeting

Credits are consumed per request, and the cost scales with how many markets and
regions you ask for at once. With WNBA props requiring one call per game:

```
15 teams → up to ~7 games on a full slate
7 games × 1 snapshot × 1 market ≈ 7 credits
7 credits × 4 snapshots/day × 30 days ≈ 840 credits/month
```

That fits comfortably in a 20,000-credit plan, which means you can afford to snapshot
far more often. Do the arithmetic in `config.yaml` rather than guessing, and log your
remaining quota — the API returns it in response headers, so print it after every run
and you'll never be surprised.

### 6.4 What to store

Store **every snapshot**, not the current state. This is a time series and its value
is in the movement.

**`odds_snapshots`**:
```
snapshot_id, captured_at_utc, game_id, book, market,
player_name_raw, line, over_price, under_price, is_alternate
```

Notes:
- `captured_at_utc` is the most important column in the table. Everything you can
  legitimately claim later depends on knowing exactly when a price existed.
- Keep `player_name_raw` exactly as the book spelled it. Do your name mapping in a
  separate step, into a separate column. Never overwrite the source string.
- Store prices as American odds integers or decimal floats, consistently. Pick one
  in `config.yaml`.
- A book may offer several lines for the same player and market. Keep them all.

### 6.5 Capture cadence

Snapshot on a schedule, not when you happen to think of it:

| Snapshot | Why |
|---|---|
| Line open (as early as posted) | Widest, softest prices |
| Midday | Baseline |
| ~1 hour before tip | Post-injury-news |
| **As close to tip as you can manage** | **This is your closing line.** |

The closing line is the single most important capture. It is the market's final,
best-informed estimate, and it is the yardstick against which everything you do gets
measured (§9.5). If you can only afford one snapshot, make it that one.

### 6.6 If you already have a hand-kept log

If you've been tracking props in a spreadsheet, that's a real asset — but audit it
before trusting it. Have your agent inventory it without interpreting it: every
sheet, every column, header text, types, null counts, sample values, and the first
and last twenty rows verbatim. Then classify what's actually present versus absent
— player, date, market, line, price, book, capture time, side taken, result — and
say "not present" rather than deriving anything.

Then reason about what it can support:

- **If it only contains props you bet**, it is a record of your behavior, not a
  sample of the market. It cannot estimate how often the model finds edges, and it
  cannot measure market efficiency.
- **If prices are missing**, nothing expected-value related can be computed. Line-only
  data supports "which side was correct," and nothing more.
- **If capture time is missing or inconsistent**, these are not closing lines and
  cannot be used for closing-line value.
- **Coverage almost certainly varies over time** because your tracking habits changed.
  Report field completeness by month, not overall.

And check depth per cell, not in total. Eight thousand rows sounds like plenty; split
across five markets and 150 players it's 10 observations per player-market pair,
which supports very little.

### 6.7 Agent prompt for phase 2

```
Build the odds ingestion layer.

- Provider: The Odds API at the-odds-api.com. Key is in .env as ODDS_API_KEY.
  Never print the key. Never write it to a file.
- WNBA player props are on the event-odds endpoint, one game per call.
  Start with a single market, configurable in config.yaml. Default: player_points.
- Save every raw response to data/raw/odds/<ISO8601 timestamp>.json before parsing.
- Build an odds_snapshots table. Store EVERY snapshot; never update in place.
  Preserve the book's original player name spelling in a raw column untouched.
- Record and print remaining API quota from the response headers after every run.
- Compute and print projected monthly credit usage at the current cadence, so I
  can see before I automate whether I'm going to blow through my plan.
- Support a --dry-run flag that parses the most recent saved raw file instead of
  calling the API, so I can develop the parser without burning credits.
- Handle: no games today, a game with no props posted, a book missing a market,
  and an HTTP error. None of these should crash the run. Log and continue.

Stop when I can run it, see a snapshot land in the database, and re-run with
--dry-run without touching the network.
```

---

## 7. Phase 3 — Cleaning, joining, and validation

**Goal:** one trustworthy table where every prop line sits next to the actual result,
and you know precisely how many rows you lost getting there and why.

This phase is boring and it is where projects die. Budget real time for it.

### 7.1 The join you are trying to make

```
odds_snapshots  ──join on (player, date)──►  player_games
```

Simple in concept. In practice this join is the primary source of silent, invisible,
project-destroying error, because **a failed join drops rows quietly** and your model
trains happily on the 60% that matched.

### 7.2 Name matching

Sportsbooks and stats providers do not agree on how to spell people. You will
encounter, for the same person:

- `A'ja Wilson` / `Aja Wilson` / `A`ja Wilson` (different apostrophe characters)
- `Kelsey Plum` / `K. Plum` / `Plum, Kelsey`
- Suffixes, hyphens, accented characters, and double surnames handled inconsistently
- Two players on different teams with the same last name
- Occasionally, two players with the same full name

**Do not fuzzy-match and move on.** Build an explicit crosswalk table:

```
name_map: raw_name, source, player_id, confidence, mapped_by
```

Process:
1. Try exact match after light normalization (unicode NFKD, strip punctuation,
   collapse whitespace, lowercase).
2. For non-matches, try match-within-team-and-date. A book's `K. Plum` on a Aces
   game night is unambiguous given the roster.
3. For what's left, use fuzzy matching to **propose** candidates, and print them for
   you to approve. Never auto-accept.
4. Persist every approved mapping so you approve each name exactly once, ever.

### 7.3 The unmatched report

**Non-negotiable.** Every clean run writes `reports/unmatched.md`:

- Every odds row that found no player-game, with the raw name and date
- Every player-game with no odds row (expected — not every player gets props)
- Match rate overall, by book, by month, and by team
- The top 20 unmatched names by frequency

Then look at it. A match rate that drops from 96% to 71% in July means something
changed — a book started spelling names differently, a new team's players aren't in
your crosswalk, a schema shifted. You will only ever catch that if you read the
report.

### 7.4 Timezone handling

WNBA games are scheduled in US Eastern; APIs return UTC. A 10:00 PM Pacific tip is
already the next calendar day in UTC. If you join on a naively-converted date, West
Coast games silently attach to the wrong day.

Rules:
- Store everything in the database as **UTC**, with explicit timezone info.
- Derive a separate `game_date_et` column and join on that.
- Never do date arithmetic on strings.
- Toronto plays in Eastern; Portland in Pacific — the league now spans four
  time zones plus an international border.

### 7.5 Other cleaning decisions

**Whole-number lines.** A line of 15 (not 15.5) can push. Your model outputs
P(over), P(under), *and* P(exactly 15). Decide how to handle pushes and write it in
`DECISIONS.md`. Most people exclude push-eligible lines from evaluation early on.

**Alternate lines.** Books offer ladders (15.5, 17.5, 19.5, "20+"). Flag these
separately. Mixing them into the main line series corrupts your sense of what the
market thinks.

**Multiple books.** Different books post different lines simultaneously. Do not
average them into a "consensus" and forget the spread — the disagreement is signal,
and the best available price is what you'd actually bet.

**Line moves.** Sequential snapshots for the same player-market are the same market
at different times. Model them as a time series, not as independent observations.

**Voided props.** A player who is scratched has their props voided. These rows have a
line but no result. Mark them explicitly; do not treat them as zeros. This is a
classic and catastrophic bug — a scratched star with a 21.5 line becomes an "under"
in a careless pipeline, and unders start looking wildly profitable.

### 7.6 Agent prompt for phase 3

```
Build the cleaning and joining layer.

- Join odds_snapshots to player_games on player identity and Eastern-time game date.
- Name matching:
    exact match on normalized names first
    then match within team+date
    then fuzzy-PROPOSE candidates and print them for my approval — never auto-accept
    persist all approvals to a name_map table so I approve each name once ever
- Store everything in UTC in the database. Derive game_date_et and join on that.
- Write reports/unmatched.md every run: unmatched odds rows, unmatched player-games,
  match rate overall and by book and by month, and the top 20 unmatched names.
- Flag and handle explicitly, with a column each:
    whole-number lines (push possible)
    alternate/ladder lines
    voided props where the player did not play — these are NOT unders
- Print before/after row counts at every step. If a step drops rows, say how many
  and why.
- Do not silently drop anything. If you can't match a row, keep it with a null and
  a reason code.

Stop when I can read reports/unmatched.md and understand exactly what was lost.
```

---

## 8. Phase 4 — Features

**Goal:** for every player-game, a row of predictors computed using only information
that existed before tip-off.

### 8.1 The leakage rule

**Features for game N may use data from games 1 through N−1 only.**

This sounds obvious and is violated constantly. Common leaks:

- Season averages computed over the *whole* season, including future games
- Team pace computed from the full season and applied to March
- "Player was on a hot streak" computed with hindsight
- Rolling windows that use `center=True` in pandas
- Opponent defensive rating from the full season
- Any standardization (`StandardScaler`) fit on the full dataset before splitting
- Filling missing values with a column mean computed over all rows

The last two are subtle and extremely common — they leak the *distribution* of the
future into the past. Any fitting must happen inside the training fold.

**Enforce this in code.** Have the agent write a test that, for a random sample of
player-games, asserts every feature is reproducible from data with an earlier
timestamp. If your backtest looks great and this test doesn't exist, assume you leaked.

### 8.2 Feature families

**Player form (with proper shrinkage):**
- Trailing 3, 5, 10-game per-40 rates for each stat
- Season-to-date per-40 rate
- Exponentially weighted rate with a configurable half-life
- Games played this season — a direct measure of how much you should trust the above

**Role and usage:**
- Usage rate: share of team possessions ended by this player
- Started (yes/no), and trailing start rate
- Minutes share: minutes ÷ 200
- Shot distribution: rim / mid / three, and free throw rate

**Team context:**
- Team pace, shrunk toward league average by games played
- Team offensive and defensive rating
- Projected total and spread for the game, if you have game lines — these encode
  the market's pace and blowout expectations for free and are strong features

**Opponent:**
- Defensive rating, opponent pace
- Positional defense: what the opponent allows to players in this role
- Careful: with 15 teams and 44 games, opponent-specific effects have tiny samples.
  Shrink hard.

**Situational:**
- Days rest (capped, and **handle the FIBA break** — treat >7 days as its own
  category rather than a continuous value)
- Back-to-back flag
- Home/away
- Travel: time zones crossed since last game
- Game number in season

**Teammate availability — the highest-value family:**
- Teammates out, weighted by their usual minutes
- Total minutes vacated by absences
- Same-position minutes vacated (a guard out helps guards)
- Whether the team's primary ball-handler is out
- Historical performance of this player in games where teammate X was out — this
  is powerful and has a brutally small sample, so shrink aggressively or you're
  fitting noise

### 8.3 Shrinkage, in plain terms

A player with 6 games at 4.2 assists per 40 has not shown you they're a 4.2-assist
player. They've shown you something between 4.2 and the league average for their
role, closer to league average the fewer games you have.

Shrunk estimate:

```
estimate = (n × observed + k × prior) / (n + k)
```

where `n` is games observed, `prior` is the league or role average, and `k` is a
tuning constant representing "how many games of evidence the prior is worth."

Tune `k` on your validation folds. In a 44-game season with mid-season projection,
`k` will be meaningfully large — the prior does a lot of work. If your agent picks
`k=1` because that's the default in some example, the model will chase hot streaks
all season.

### 8.4 Agent prompt for phase 4

```
Build the feature layer.

HARD CONSTRAINT: features for game N use only data from games 1..N-1 plus pregame
roster/injury info. Enforce this in code. Write a test that samples 50 random
player-games, recomputes each feature from an as-of-date snapshot, and asserts
equality. Any scaler, imputer, or encoder must be fit inside the training fold only.

Build these families, all computed as-of:
  player form: trailing 3/5/10 and EWM per-40 rates, plus games_played
  role: usage rate, start rate, minutes share, shot mix, FT rate
  team: pace, offensive and defensive rating, all shrunk by games played
  opponent: defensive rating, pace, positional defense — shrink hard, only 15 teams
  situational: rest days (treat >7 as its own category for the FIBA break),
    back-to-back, home/away, time zones crossed, game number
  teammate availability: minutes vacated by absences, same-position minutes
    vacated, primary ball-handler out flag

Implement shrinkage as (n*observed + k*prior)/(n+k). Put every k in config.yaml.
Print the effective shrinkage weight per player so I can see how much the prior is
doing.

Print a feature summary table: name, coverage %, mean, sd, min, max, and count of
nulls. Flag any feature with >20% nulls or zero variance.
```

---

## 9. Phase 5 — The minutes model

**Goal:** a probability distribution over minutes played, for every player who might
play tonight.

This is the most important model in the project. Get this right and mediocre rate
models still produce decent props. Get it wrong and perfect rate models produce
garbage.

### 9.1 Structure: two stages

Minutes have a spike at zero (DNPs) and a continuous distribution above it. One
model cannot handle both well. Split it:

```
P(minutes = 0)        →  a classifier
P(minutes | plays)    →  a continuous distribution on (0, 40]
```

Combine them for the full distribution. When you simulate, draw the coin flip first,
then the minutes.

### 9.2 The sum constraint — use it

Team minutes must total exactly 200 in regulation. This is free information and most
naive models throw it away, producing rosters that sum to 214. If the model prices
props that include overtime, first simulate a game-level overtime event, then add 25
team-minutes for each simulated overtime period; do not add overtime to every pregame
simulation.

The clean approach: model **minutes share** rather than raw minutes.

```
For each team-game:
  sample a share vector over active players from a Dirichlet distribution
  minutes_i = share_i × 200
```

The Dirichlet's concentration parameter controls how much rotation variance you get.
Fit its parameters from historical rotations conditioned on who's active. This
guarantees the constraint holds in every simulation, and it naturally produces the
correlation you want — when one player's minutes come in high, someone else's must
come in low.

If a Dirichlet is more machinery than you want at first, a workable simpler version
is: model each player's minutes independently, then normalize the team's draws to sum
to 200. Cruder, and it distorts the tails, but it's a legitimate starting point.

### 9.3 What drives minutes

In rough order of importance:

1. **Recent minutes** — trailing 3–5 games, weighted toward most recent
2. **Who else is available** — the dominant factor when a rotation player is out
3. **Started or not**
4. **Game script** — blowouts collapse starter minutes; close games extend them
5. **Rest** — back-to-backs, and load management for veterans
6. **Foul trouble** — largely unpredictable pregame, but it fattens the left tail
7. **Injury return** — players coming back are often on explicit minutes restrictions,
   which beat reporters announce and your model cannot infer

### 9.4 Game script — a subtlety worth getting right

Blowouts cut starter minutes substantially. This creates a real correlation: a player
on a heavy favorite has a **fatter left tail** in minutes than the same player in a
close game.

If you have game lines, the spread is an excellent proxy for blowout probability and
you should use it directly. If you don't, team strength differential works.

This is one reason to model minutes and rates jointly through simulation rather than
multiplying two independent point estimates — the correlation between game state and
minutes is real and material for star players on big favorites.

### 9.5 Evaluating the minutes model

Do this before touching rate models. If minutes aren't calibrated, nothing downstream
can be.

- **MAE of the median** — how far off is your central estimate?
- **Interval coverage** — do your 50/80/95% intervals contain the truth 50/80/95% of
  the time? Report all three. This is the check that matters.
- **DNP classification** — log loss and calibration on the "will they play" model
- **Sum check** — do simulated team minutes total 200 in every simulation?
- **Beat the baselines** — trailing-5-game average minutes, and last game's minutes.
  If you can't beat trailing-5, your model is not adding information.

### 9.6 Agent prompt for phase 5

```
Build the minutes model.

Two-stage:
  1. classifier for P(minutes = 0), given availability and recent rotation
  2. continuous distribution for minutes | plays, on (0, 40]

Model minutes SHARE, not raw minutes. Sample a share vector per team-game from a
Dirichlet over active players, then multiply by 200 in regulation. If you have an
explicit game-level overtime model, add 25 per simulated overtime period. Assert the
team-minute total in every simulation.

Note: WNBA games are 40 minutes, so a team plays 200 player-minutes, not 240.
Do not use per-36 conventions anywhere.

Condition on: trailing 3/5/10 minutes, started flag, minutes vacated by absent
teammates, same-position minutes vacated, rest days, back-to-back, and the game
spread if available (as a blowout proxy — heavy favorites should show a fatter
left tail for starters).

Evaluate before I move on:
  MAE of the median prediction
  coverage of 50/80/95% intervals — report all three
  log loss and a calibration plot for the DNP classifier
  a test asserting simulated team minutes always sum to 200 (+OT)
  comparison against two baselines: trailing-5-game mean minutes, and last game's
    minutes. Print all three side by side.

If the model does not beat trailing-5 on both MAE and coverage, say so plainly
and stop rather than proceeding.
```

---

## 10. Phase 6 — Rate models

**Goal:** distributions over production per unit of playing time.

### 10.1 Why not just use the average

Because you need the shape, not the center. Two distributions with the same mean give
different answers to "what is P(≥ 19)?"

### 10.2 Distribution choice, by stat

**Three-pointers made** — the cleanest place to start:

```
3PM ~ Binomial(3PA, p3)
```

Model attempts and accuracy separately. `3PA` is a count (per-40, scaled by the
minutes draw); `p3` is a probability that should come from a Beta prior shrunk toward
the player's role and league average. Small-sample three-point percentage is
notoriously unstable — a player shooting 6-for-12 has not shown you 50%. Beta-binomial
handles this naturally.

**Rebounds and assists** — negative binomial.

The default instinct is Poisson. **Poisson is wrong here** and specifically wrong in a
direction that hurts you: Poisson forces variance = mean, but real rebound and assist
counts are *overdispersed* (variance > mean). Using Poisson gives you a distribution
that is too narrow, which systematically overstates your confidence and makes low
lines look like automatic overs.

Negative binomial adds a dispersion parameter. Fit it. Check it — compute the observed
variance-to-mean ratio in your data; if it's meaningfully above 1, you need NB.

**Points** — do not model directly.

Points are a compound quantity:

```
PTS = 2 × 2PM + 3 × 3PM + FTM
```

Model the components and add them in simulation. This automatically produces the
correct lumpy, multi-modal shape that a smooth continuous distribution cannot. It also
means improvements to your three-point model propagate to points for free.

**Combos (PRA, P+R, R+A)** — never model the sum directly.

Simulate the components with their correlations and add them per-simulation. The
components are correlated — a player who plays 38 minutes gets more of everything, and
a high-usage night lifts points and assists together. Fitting the sum directly throws
that structure away and gets the tails wrong, which is exactly where the money is.

### 10.3 Hierarchical structure

With 44 games, individual player estimates are noisy. Use partial pooling:

```
league average  →  role/position average  →  player estimate
```

Each level shrinks toward the one above, with the amount of shrinkage determined by
how much data the player has. A rookie in her 8th game gets pulled hard toward the
role prior; a veteran in game 40 mostly stands on her own.

You can implement this properly with `PyMC` or `numpyro`, which gives you full
posteriors and honest uncertainty. Or you can approximate it with empirical-Bayes
shrinkage formulas, which is much faster to fit and much easier to debug. **Start with
the approximation.** Get the whole pipeline working end to end, then upgrade the
component that most needs it.

### 10.4 Opponent and pace adjustments

Adjust rates for opponent, but adjust *gently*. With 15 teams and 44 games, a player
has faced any given opponent a handful of times. Opponent effects estimated from that
are mostly noise.

Team-level opponent effects (this team allows more threes than average) are estimable.
Player-vs-team effects are almost never estimable at this sample size, however
tempting the narrative. If your agent proposes a player-opponent interaction term,
ask how many observations support it.

### 10.5 Agent prompt for phase 6

```
Build the rate models. Start with ONE stat and get it fully working before adding
others.

Order: three-pointers made, then rebounds, then assists, then points.

3PM: Binomial(3PA, p3). Model 3PA per-40 separately. p3 from a Beta prior shrunk
  toward role and league average. Print the shrinkage weight per player.

Rebounds and assists: negative binomial per-40, NOT Poisson. First compute and
  print the observed variance-to-mean ratio in the data to justify this. If it is
  near 1, tell me and reconsider.

Points: do NOT model directly. Model 2PM, 3PM, and FTM separately and sum them in
  simulation.

Combos (PRA etc.): do NOT fit the sum. They come out of the simulation in phase 7.

Use hierarchical partial pooling: league -> role -> player. Start with empirical
Bayes shrinkage rather than full MCMC. Print effective sample size and shrinkage
weight per player so I can see the prior's influence.

Opponent adjustments at the TEAM level only. Do not build player-vs-opponent
interactions — there aren't enough observations. If you think one is justified,
tell me the sample size first.

Evaluate each rate model on held-out games before adding the next stat:
  CRPS against realized values
  PIT histogram (should be flat — if it's U-shaped your distributions are too
    narrow, if it's peaked they're too wide)
  comparison against baselines: season-to-date rate, trailing-10 rate
```

---

## 11. Phase 7 — Simulation

**Goal:** a joint distribution over every stat for every player in a game.

### 11.1 Why simulate

Three reasons closed-form math can't cover:

1. **Combo props.** PRA requires the joint distribution, not three marginals.
2. **Uncertainty propagation.** Minutes uncertainty has to flow into stat
   uncertainty. Multiplying a minutes point-estimate by a rate point-estimate
   throws away the variance that matters most.
3. **Correlation.** Teammates' outcomes are linked — minutes are zero-sum, shots are
   partly zero-sum, and game pace lifts everyone together.

### 11.2 Simulation structure

For each game, repeat N times:

```
1. Sample game pace → total possessions for each team
2. Sample the minutes share vector for each team (Dirichlet) → player minutes
3. For each player:
     sample usage share, conditional on who's on the floor
     sample shot attempts from minutes × pace × usage
     sample makes from attempts × shooting rates
     sample rebounds, assists from per-40 rates × minutes
4. Compute all derived stats (points, PRA, etc.) for this simulation
5. Store the full result
```

After N simulations you have an empirical distribution for every stat for every
player, and every prop question is a counting operation:

```
P(points ≥ 19) = (simulations where points ≥ 19) / N
```

Combos, alternate lines, and correlated same-game questions all fall out for free.

### 11.3 Practical parameters

- **N = 10,000** is enough for main lines. **N = 50,000** if you care about tails
  (deep alternate lines, milestone markets).
- **Set a seed** and store it. Reproducibility matters when you're debugging why
  yesterday's number was different.
- **Vectorize.** Loops in Python over 50,000 simulations × 12 players × 7 games will
  be slow enough to discourage you from iterating. Numpy arrays over the whole slate
  at once.
- **Store the summary, not every simulation.** Percentiles at 1-point intervals plus
  the mean and sd is plenty and is a tiny fraction of the storage.

### 11.4 Sanity checks

- Simulated team points should roughly match the game total line, if you have one
- Simulated team minutes sum to 200 in regulation; add 25 only after an explicit
  simulated overtime event
- Simulated player rebounds summed across both teams should be near the realistic
  team rebound range, not double it
- Simulated distributions for known players should look like their actual game logs —
  plot them on top of each other and look

That last one is the best debugging tool in the project. Overlay the simulated
distribution against the player's actual season game log. If your simulation says a
player scores 25+ in 30% of games and she's done it twice in 40, something is wrong.

### 11.5 Agent prompt for phase 7

```
Build the Monte Carlo simulation layer.

Per game, N simulations (config, default 10000):
  1. sample pace -> possessions per team
  2. sample the Dirichlet minutes-share vector -> player minutes summing to 200
  3. per player: usage share -> shot attempts -> makes; rebounds and assists from
     per-40 rates scaled by that simulation's minutes
  4. derive points from 2PM/3PM/FTM, and all combos, per simulation

Vectorize with numpy across the whole slate. Set and store a random seed.

Store per player: percentiles at 1-unit intervals, mean, sd — not the raw draws.

Sanity checks, printed every run:
  team minutes sum to 200 in regulation; add 25 only after an explicit simulated
    overtime event
  simulated team points vs. the posted game total, if available
  for 5 named players I pick, overlay the simulated distribution against their
    actual season game log and save the plot to reports/

Output P(stat >= k) for a range of k around each posted line.
```

---

## 12. Phase 8 — Pricing: de-vigging, edge, and sizing

**Goal:** turn a model probability and a market price into a decision.

### 12.1 The vig

A book posting a prop at −115 / −115 is not offering a 50/50. Convert to implied
probabilities:

```
American odds → implied probability
  negative odds:  p = (−odds) / (−odds + 100)
  positive odds:  p = 100 / (odds + 100)
```

At −115 / −115, both sides imply 53.5%, summing to **107%**. That extra 7% is the
hold. Props routinely run 6–12%, versus roughly 4.5% on standard sides.

**You must remove the vig before comparing anything.** A model that says 54% on a
−115 side is not finding an edge — the market's true estimate there is about 50%,
and 54% is a real but small edge. If you compare your 54% to the raw 53.5% implied,
you'll think you have 0.5% and bet nothing. If you don't de-vig at all, every
calibration statistic you compute will be wrong.

### 12.2 De-vigging methods

Given raw implied probabilities `q_over`, `q_under` summing to more than 1:

**Multiplicative (proportional).** Divide each by the sum.
```
p_over = q_over / (q_over + q_under)
```
Simple. Fine for balanced two-way markets. Known to be biased on lopsided markets —
it under-prices favorites relative to reality.

**Additive.** Subtract the excess equally from both sides. Generally worse than
multiplicative; not recommended.

**Power / logarithmic.** Find the exponent `k` such that `q_over^k + q_under^k = 1`.
Handles lopsided markets better. Requires a one-dimensional root solve, which is
about four lines of code with `scipy.optimize.brentq`.

**Shin.** Models the market as containing some proportion of informed traders and
solves for the true probabilities under that assumption. Best-regarded for longshots.
More machinery.

**Practical guidance:** on a −115 / −115 prop all four methods agree to within a
fraction of a percent. On a −250 / +190 prop they diverge meaningfully. Start with
multiplicative, implement power as an option in `config.yaml`, and check whether your
results are sensitive to the choice. If they are, that's informative in itself.

### 12.3 Best price, not average price

Different books post different lines and prices at the same moment. What you'd
actually get is the best available number. Compute:

- **Fair probability** from the sharpest available book, or a de-vigged consensus of
  several
- **Edge** against the *best* price you could actually take

Conflating "the market's estimate" (use consensus or a sharp book) with "the price
I can get" (use the best) is a common and costly error in both directions.

### 12.4 Edge and sizing

```
edge = model_p_over − fair_p_over
```

For sizing, Kelly:

```
f* = (p × b − (1 − p)) / b
```
where `p` is your win probability and `b` is decimal odds minus 1.

**Use a fraction of Kelly — a quarter is standard.** Full Kelly assumes your
probability estimate is correct. Yours is not. Kelly is extremely punishing when `p`
is overestimated, and every new modeler overestimates `p`. Quarter Kelly gives up a
little growth for a large reduction in ruin risk.

Also set an **edge floor**. Bets with a computed 0.4% edge are noise — the difference
between 0.4% edge and 0% edge is far smaller than your model error. A floor of 2–3%
is a reasonable starting point, and you should tune it on validation data, not vibes.

### 12.5 Agent prompt for phase 8

```
Build the pricing layer.

- Convert American odds to implied probability. Compute and print the hold on every
  two-way market so I can see what I'm up against.
- De-vig. Implement multiplicative and power methods; select via config.yaml.
  Print both for each market so I can see how much the choice matters.
- Distinguish clearly between:
    fair probability (from a sharp book or de-vigged consensus)
    best available price (what I could actually bet)
  Compute edge as model probability minus fair probability, and expected value
  against the best available price.
- Kelly sizing at a configurable fraction, default 0.25. Print both full and
  fractional so I can see the difference.
- Apply a configurable minimum edge threshold, default 3%.
- Output a CSV of today's slate sorted by edge with columns: player, market, line,
  best price, book, model P(over), fair P(over), edge, quarter-Kelly stake.

Do not produce a bankroll graph or a profit projection. I have not established
that the model works yet.
```

---

## 13. Phase 9 — Evaluation and calibration

**Goal:** find out whether the model is any good, honestly.

This is the phase where you find out you wasted six weeks, which is exactly why it
has to be rigorous and why it must not come last in your thinking, even though it
comes last in the build.

### 13.1 Walk-forward, always

**Never use a random train/test split on time series data.** Random splits let the
model train on August and predict June, which is impossible in reality and produces
results that look wonderful and mean nothing.

Walk-forward:

```
train on games through June 15  →  predict June 16-22
train on games through June 22  →  predict June 23-29
train on games through June 29  →  predict June 30 - July 6
...
```

Accumulate the out-of-sample predictions and evaluate on all of them together. This
mirrors how the model would actually have been used.

**Hold out the last three weeks entirely.** Do not look at them. Do not evaluate on
them. Do not tune anything on them. They exist so that at the very end you get one
honest read. Every time you look at them and then change something, they become
training data and you've spent your only unbiased measurement.

### 13.2 Metrics that measure the distribution

**CRPS (Continuous Ranked Probability Score)** — the primary metric. It scores a full
predicted distribution against a single realized value, rewarding both accuracy and
appropriate sharpness. Lower is better. It's the right generalization of absolute
error to distributional forecasts.

**PIT histogram** — take each realized value's percentile in its predicted
distribution and histogram them across all predictions. If your distributions are
right, this is **flat**.

Read it like this:
- **U-shaped** (too many values in the tails) → distributions are too narrow. You're
  overconfident. Very common. Usually means Poisson where you needed negative
  binomial, or minutes variance too low.
- **Peaked in the middle** → distributions are too wide. Less common.
- **Sloped** → systematic bias, over- or under-projecting.

**Interval coverage** — do 50/80/95% intervals contain the truth 50/80/95% of the
time? Report all three. A model that's calibrated at 50% but not 95% has tail
problems, which is precisely where props live.

### 13.3 Metrics that measure the bet

**Log loss and Brier score** on the binary over/under, versus the posted line.

**Reliability diagram** — bucket predictions by predicted probability (0–5%, 5–10%,
… 95–100%) and plot predicted versus observed frequency. On the diagonal is
calibrated. A model that says 65% and hits 52% is not calibrated, and no amount of
Kelly sizing will save it.

This is more important than accuracy. A calibrated model that's rarely confident is
useful. An overconfident accurate model will bankrupt you.

### 13.4 Baselines you must beat

Your model is not "good" in the abstract. It's good relative to something. Run all
of these and print them side by side:

| Baseline | What it is |
|---|---|
| 1. Season average | Player's season-to-date mean for the stat |
| 2. Trailing 10 | Mean of last 10 games |
| **3. Rate × minutes** | **Trailing-10 per-40 rate × your projected minutes** |
| 4. The market | The de-vigged line itself as a probability |

**Baseline 3 is the real bar** and most models lose to it. It's cheap, it captures
the single most important structural insight (minutes × rate), and if all your
hierarchical modeling can't beat it, your hierarchical modeling isn't doing anything.

**Baseline 4 is the honest bar.** If you cannot beat the market's own implied
distribution out of sample, you have no edge. That's not a failure — most models
don't, and knowing it is worth more than a bankroll graph.

### 13.5 CLV — the metric that actually matters

**Closing Line Value** compares the price you took to the closing price on the same
market.

If you bet an over at +100 and it closes at −120, you got positive CLV: the market
moved toward your position after you bet. Consistent positive CLV is the strongest
available evidence that you're finding real inefficiency, and it converges **far**
faster than profit does.

**Why it matters more than ROI:**

At −110, breakeven is 52.38%. To distinguish a genuine 55% win rate from 50% at
conventional confidence, you need roughly a thousand bets just for the point estimate
to exclude coin-flipping, and several thousand for reasonable power to detect it. At
a handful of qualifying bets per slate, that is **more than one full WNBA season**,
probably two.

You do not have that. You will never have enough bets to distinguish skill from luck
by profit alone in a 44-game season. CLV gives you a usable signal in weeks instead of
years.

**This is why §6.5 insisted on capturing closing lines.** Without them, this metric
does not exist for you.

### 13.6 What not to report

Have your agent explicitly refuse to produce these until the model has cleared the
baselines out of sample:

- **Bankroll curves.** Emotionally compelling, statistically meaningless at your
  sample size, and the single fastest way to talk yourself into a broken model.
- **ROI over a few hundred bets.** Noise.
- **"Units won."** Same problem, worse framing.
- **Any backtest against non-closing lines.** If you don't know when the price was
  captured, you can't compute anything meaningful about profit.

### 13.7 Agent prompt for phase 9

```
Build the evaluation layer.

Walk-forward only. Retrain weekly, predict the following week, roll forward.
Never a random split. Freeze the final 3 weeks as an untouched holdout — do not
evaluate on it, do not tune on it, and warn me if I ask you to.

Distributional metrics:
  CRPS against realized values, overall and by market and by minutes bucket
  PIT histogram, saved to reports/. Tell me in words what the shape means.
  interval coverage at 50/80/95%

Binary metrics vs. the posted line:
  log loss, Brier score
  reliability diagram saved to reports/

Baselines — run all four, print side by side in one table:
  1. season-to-date average
  2. trailing-10 average
  3. trailing-10 per-40 rate x my projected minutes
  4. the de-vigged market line as a probability
State plainly whether the model beats each. Do not soften a loss.

CLV: for every bet the model would have made, compare the price taken to the
closing price on that market. Report mean CLV in cents and the percentage of bets
with positive CLV. If closing lines are unavailable, say so and skip it — do not
substitute a different price and call it closing.

Do NOT produce a bankroll curve, ROI, or units-won under any circumstance in this
phase. If I ask for one, remind me that my sample size cannot support it.
```

---

## 14. Phase 10 — Hosting and automation

**Goal:** it runs every day without you.

Do not do this early. An automated pipeline feeding a broken model just produces
wrong answers faster. But once the model works, manual operation decays fast — you'll
skip a day, then a week, and your odds archive gets holes in it.

### 14.1 The tiers

**Tier 0 — Manual (start here, stay a while)**

You type `python run.py update && python run.py project` each morning. Zero cost,
zero infrastructure, complete visibility. Stay here through phase 9.

**Tier 1 — Double-clickable script**

A `.command` file (Mac) or `.bat` file (Windows) that runs the sequence and leaves
output on screen. Still manual, but one click and no terminal. Half an hour of work,
meaningfully increases the odds you actually run it daily.

**Tier 2 — GitHub Actions (the sweet spot for this project)**

A scheduled workflow on GitHub's free tier. No server, no credit card.

How it works: a YAML file in `.github/workflows/` defines a cron schedule. GitHub
spins up a runner, checks out your repo, installs dependencies, runs your command,
and commits the updated database back to the repository.

Genuinely good, with real caveats:

- Scheduled workflows **do not fire precisely on time**. Delays of 10–30 minutes are
  routine and can be longer at peak. Do not schedule a closing-line capture at
  T-minus-5-minutes and expect it to land.
- GitHub **disables scheduled workflows on repositories with no activity for 60
  days**. If your daily job commits data, that counts as activity and you're fine —
  but know the rule.
- Free-tier minutes are limited on private repositories and effectively unlimited on
  public ones. A few minutes a day fits comfortably either way.
- Runs can fail silently. **Configure failure notifications.**

**Tier 3 — A small VPS**

Roughly $5/month at Hetzner, DigitalOcean, Vultr, or similar. A `cron` entry or
`systemd` timer runs your script. Full control, precise timing, and you now own a
Linux box you must keep patched. Reasonable if Actions' timing imprecision bothers
you, which it should if you're serious about closing-line capture.

**Tier 4 — Managed platforms**

Modal, Railway, Render, Fly.io. Scheduled jobs, generous free tiers, less
administration than a VPS. More platform-specific concepts to learn. Fine, but for a
project this size Tier 2 or 3 usually wins.

### 14.2 Comparison

| | Cost | Setup | Timing precision | You maintain |
|---|---|---|---|---|
| Manual | $0 | none | whenever you remember | nothing |
| Double-click script | $0 | 30 min | whenever you click | nothing |
| GitHub Actions | $0 | 1–2 hrs | ±10–30 min | a YAML file |
| VPS + cron | ~$5/mo | 2–4 hrs | precise | an OS |
| Managed platform | $0–10/mo | 1–3 hrs | precise | a config |

### 14.3 Where the database lives

Once you automate, "where does the SQLite file live" becomes a real question.

- **GitHub Actions:** commit the `.db` file back to the repo after each run. Works
  well while the file is small (under ~50 MB comfortably; Git warns past 50 MB and
  hard-limits at 100 MB). Your `.gitignore` from §3.3 excludes `*.db`, so you'll need
  an explicit exception when you get here — note the change in `DECISIONS.md`.
- **Approaching the size limit:** store only the cleaned tables in git and keep raw
  JSON elsewhere, or move to Turso (hosted SQLite, free tier) or Supabase (hosted
  Postgres, free tier).
- **VPS:** the file just lives on disk. Back it up (see below).

### 14.4 Backups

**Back up the odds archive you collect.** A provider may offer historical odds, but
coverage varies by plan, bookmaker, market, and time period. Do not assume the exact
July 14 snapshot you captured can be restored later.

Minimum viable backup:
- Raw JSON responses committed to a separate repository, or synced to cloud storage
- A weekly database dump to somewhere that is not the machine running the job
- Verify the backup restores. An unverified backup is a hope, not a backup.

### 14.5 Monitoring

Automation you don't monitor is worse than manual operation, because it fails
silently and you find out three weeks later that your archive has a hole in it.

- Every run writes a status line: timestamp, records fetched, errors, quota remaining
- Failures notify you — GitHub Actions can email on failure; a webhook to a Discord
  or Slack channel works too
- A weekly heartbeat summary: how many days ran successfully, days missed, quota used
- **A staleness check:** if the newest odds snapshot is more than 36 hours old, alert
  loudly. This is the check that catches the silent failures.

### 14.6 Agent prompt for phase 10

```
Set up automation. Assume I have never used any of this.

Start with Tier 1: a double-clickable file for my OS that runs update + project and
leaves the output visible. Explain exactly where to put it and how to make it
executable.

Then Tier 2: a GitHub Actions workflow.
  - Explain what each block of the YAML does, line by line. Assume zero knowledge.
  - Schedule multiple daily runs; tell me the UTC cron for each, given I want them
    at specific Eastern times, and remind me about daylight saving.
  - Warn me explicitly that scheduled workflows are frequently delayed 10-30 minutes,
    and help me pick capture times that tolerate that.
  - Store ODDS_API_KEY as a GitHub Secret. Show me where in the UI to add it.
    Never put it in the YAML.
  - Commit the updated database back to the repo after each run. Tell me what to
    change in .gitignore to allow this, and what the size limits are.
  - Configure email notification on failure.

Monitoring:
  - Every run logs timestamp, records fetched, errors, and remaining API quota.
  - A staleness check: if the newest odds snapshot is more than 36 hours old, fail
    the run loudly rather than exiting quietly.
  - A weekly summary of days run, days missed, and quota consumed.

Backups:
  - A weekly database dump plus raw JSON to a location separate from the runner.
  - Write me a short RESTORE.md with the exact steps to rebuild from backup, and
    make me test it once.
```

---

## 15. Operating it

The build ends; the operation doesn't.

**Daily:** confirm the run completed. Glance at the projections CSV. Check that
today's slate has the right number of games.

**Weekly:** read `reports/unmatched.md`. Retrain. Check calibration hasn't drifted.
Confirm the backup ran.

**Monthly:** full walk-forward re-evaluation. Compare against the baselines again —
a model that beat baseline 3 in June may not in August as rosters and rotations
change. Review API spend.

**When something looks wrong:** the answer is almost always in the data layer, not
the model. Check the join rate first. Then check for schema changes at the source.
Then look at the model.

**Retraining cadence:** weekly is right for a 44-game season. Daily overfits to
noise; monthly leaves too much information on the table when a rotation change
happens.

**Season boundaries:** at the start of next season, everything changes — rosters,
teams, possibly rules. Do not assume your pipeline survives the transition. Plan a
February check-in to re-validate every ingestion path before opening night.

---

## 16. Failure modes: the catalog

Read this before you start and again when something looks too good.

### Data failures

**Silent join loss.** 40% of your odds rows don't match a player-game, the model
trains on the rest, and nobody notices. *Fix:* the unmatched report, read every week.

**Voided props counted as unders.** A scratched player's props are voided. Treated
carelessly they become unders that "hit," and your under model looks brilliant.
*Fix:* explicit void flag in phase 3, and exclude them from evaluation.

**Timezone drift.** Late West Coast games attach to the wrong date. *Fix:* UTC in
storage, an explicit `game_date_et` for joins.

**Schema change at the source.** A free API renames a field mid-season and your
parser starts writing nulls. *Fix:* validation checks on every ingest, and raw JSON
on disk so you can re-parse history.

**Missing overtime handling.** Team minutes sum to 225 and your share model produces
nonsense. *Fix:* the sum check.

### Modeling failures

**Leakage.** Season averages including the future, scalers fit before splitting,
`center=True` rolling windows. Produces spectacular backtests. *Fix:* the as-of test
in phase 4.

**Random train/test split.** Trains on August, predicts June. *Fix:* walk-forward
only.

**Poisson where you needed negative binomial.** Distributions too narrow, U-shaped
PIT, systematic overconfidence on low lines. *Fix:* check the variance-to-mean ratio.

**Per-36 in a 40-minute league.** Everything is off by 11% in a way that's just
subtle enough to survive review. *Fix:* per-40 or per-possession, and grep your
codebase for `36`.

**Not shrinking enough.** With 44 games, a model that trusts raw player rates chases
hot streaks all season. *Fix:* tune `k` on validation, and print effective shrinkage
so you can see it.

**Expansion team cold start.** No history for Toronto or Portland, so features are
null and the model either crashes or silently imputes something absurd. *Fix:*
explicit league-average fallback with heavy shrinkage, and a test that runs the
pipeline for those teams.

**Overfitting to a regime.** "Unders were printing in June, overs since July" is not
a discovered regime. It's noise in a market that reprices continuously — if one side
were genuinely mispriced for two months, the line would have moved. A model whose
evaluation output tracks whichever side ran hot recently is a model that's leaking or
overfitting, not one that found something.

### Betting-layer failures

**Not de-vigging.** Every probability comparison is wrong and every calibration
statistic is meaningless.

**Backtesting against non-closing lines.** Whatever you compute is uninterpretable.

**Full Kelly.** Assumes your probabilities are correct. They aren't. *Fix:* quarter
Kelly, and an edge floor.

**Believing ROI over 200 bets.** You need thousands to distinguish a 3% edge from
zero. *Fix:* CLV.

**Chasing stale lines that don't exist.** Your archive shows a fat edge at a book
that would have limited or voided you, or the price was gone in 40 seconds. Real
edges at real limits are much smaller than backtested ones.

### Operational failures

**IP ban from re-fetching.** A non-idempotent job hammering a free API nightly.
*Fix:* idempotency, and raw-file caching.

**Committed API key.** Rotate it — removing the file doesn't clear git history.

**Silent automation failure.** Three weeks of missing snapshots discovered too late.
*Fix:* the staleness check.

**Lost odds archive.** Your exact captured snapshots may not be recoverable from a
provider later, even when historical odds exist. *Fix:* verified backups.

---

## 17. What this costs

| Item | Cost |
|---|---|
| Stats data (sportsdataverse, stats.wnba.com) | $0 |
| Odds data for player-prop development (The Odds API, 20K credits) | ~$30/mo |
| Hosting — manual or GitHub Actions | $0 |
| Hosting — small VPS, if you want precise timing | ~$5/mo |
| Storage | $0 |
| Coding agent | varies |
| **Realistic minimum to run daily** | **~$30/mo** |

You can build the stats-only parts without an odds subscription, but meaningful
player-prop development requires a data source with enough coverage and credits.

---

## 18. Sequencing: the honest version

Rough calendar for someone with limited time and no prior experience, working
alongside an agent:

| Weeks | What |
|---|---|
| 1 | Environment, project skeleton, git. Start capturing odds **today** even with nothing else built. |
| 2–3 | Stats ingestion and validation (§5) |
| 3–4 | Odds ingestion (§6) |
| 4–5 | Cleaning, joining, the unmatched report (§7) |
| 5–6 | Features, with the leakage test (§8) |
| 6–8 | Minutes model, evaluated properly (§9) |
| 8–10 | Rate models, one stat at a time (§10) |
| 10–11 | Simulation (§11) |
| 11–12 | Pricing and de-vigging (§12) |
| 12–14 | Evaluation, calibration, baselines (§13) |
| 14+ | Automation (§14) — only if §13 went well |

**The critical path is odds capture.** You can often obtain some historical odds, but
coverage varies by plan, bookmaker, market, and timestamp. Your own snapshots are the
reliable archive for the exact lines and books you intend to evaluate. Start
snapshotting those lines before you write any model code.

---

## 19. Glossary

**Calibration** — whether stated probabilities match observed frequencies. A
calibrated 70% happens 70% of the time.

**CLV (Closing Line Value)** — the difference between the price you took and the
closing price. The best short-run evidence of edge.

**CRPS** — Continuous Ranked Probability Score. Scores a predicted distribution
against a realized value. Lower is better.

**De-vig** — removing the bookmaker's margin to recover implied true probabilities.

**Dirichlet distribution** — a distribution over vectors that sum to 1. Used here for
minutes shares so team minutes always total 200.

**Hold / vig / juice** — the bookmaker's margin. Props run 6–12%.

**Idempotent** — running twice has the same effect as running once.

**Kelly criterion** — optimal bet sizing given edge. Use a fraction of it.

**Leakage** — using information in training that wouldn't have been available at
prediction time.

**Negative binomial** — a count distribution with a free dispersion parameter.
Handles overdispersion; Poisson does not.

**Overdispersion** — variance exceeding the mean. Common in real count data.

**Partial pooling / shrinkage** — pulling noisy individual estimates toward a group
average, proportional to how little data supports them.

**PIT histogram** — Probability Integral Transform. Percentile of each observed value
within its predicted distribution. Flat means calibrated.

**Push** — a tie on a whole-number line; the bet is refunded.

**Walk-forward validation** — train on the past, test on the future, roll forward.
The only valid approach for time series.

---

## 20. One last thing

The most likely outcome of this project is that you build something well-engineered,
evaluate it honestly, and discover it does not beat the market. That is a successful
project. You will have learned distributional modeling, hierarchical shrinkage,
Monte Carlo simulation, time series validation, and how to build a data pipeline that
doesn't lie to you — all of which transfer to work that pays better than this.

The failure mode is building something that *appears* to beat the market because it
leaked, and finding out with money. Every rule in this document about validation,
holdouts, and refusing to plot bankroll curves exists to prevent that specific
outcome.

Build it in order. Read the reports. Don't believe the good news.
