# Phase 4 — Features

**Guide:** §8 (all of it), §2 for the WNBA constraints
**Prerequisite:** phase 3

## Goal

For every player-game, a row of predictors computed using only information that
existed before tip-off.

## The leakage rule

**Features for game N use data from games 1..N−1 only.** This sounds obvious and
is violated constantly. The specific leaks to avoid:

- Season averages computed over the whole season, including future games
- Team pace or opponent defensive rating from the full season, applied to June
- Rolling windows with `center=True`
- **Any scaler, imputer, or encoder fit before the split.** These leak the
  *distribution* of the future into the past. Fit inside the training fold only.
- Filling nulls with a column mean computed over all rows

**Enforce this with a test**, not with discipline: sample 50 random player-games,
recompute every feature from an as-of-date snapshot, assert equality. If the
phase 9 backtest looks great and this test doesn't exist, assume you leaked.

## Feature families

**Player form** — trailing 3/5/10-game per-40 rates, EWM rate with configurable
half-life, season-to-date per-40 rate, and `games_played` (a direct measure of how
much to trust the rest).

**Role** — usage rate, started flag and trailing start rate, minutes share
(minutes ÷ 200), shot distribution, free throw rate.

**Team** — pace, offensive and defensive rating, all shrunk toward league average
by games played.

**Opponent** — defensive rating, pace, positional defense. **Shrink hard.** With
15 teams and 44 games, opponent-specific effects are mostly noise.

**Situational** — days rest, back-to-back, home/away, time zones crossed, game
number.

⚠️ **The 2026 season has a two-week break in early September for the FIBA Women's
World Cup**, during which players compete internationally. Treat rest days >7 as
its own category rather than a continuous value — a naive computation reads
"18 days rest" and form features span a period of entirely different activity.

**Teammate availability — the highest-value family.** Minutes vacated by absences
weighted by usual playing time, same-position minutes vacated, primary
ball-handler out flag. WNBA rosters are small and minutes concentrated, so one
starter sitting reallocates to a few specific teammates rather than diffusely.
Historical performance with teammate X out is powerful and has a brutal sample —
shrink aggressively or you're fitting noise.

## Expansion teams

Toronto and Portland have no team history. Build an **explicit league-average
fallback with heavy shrinkage**, and a test that runs the feature pipeline for
those teams. Without it, features are null and the model either crashes or
silently imputes something absurd.

## Shrinkage

```
estimate = (n × observed + k × prior) / (n + k)
```

Every `k` goes in `config.yaml`. Tune on validation folds, not by defaults — in a
44-game season with mid-season projection, `k` is meaningfully large and the prior
does real work. A `k` of 1 will chase hot streaks all season.

**Print the effective shrinkage weight per player** so the user can see how much
the prior is doing.

## Definition of done

- The as-of leakage test exists and passes
- Feature summary table printed: name, coverage %, mean, sd, min, max, nulls
- Any feature with >20% nulls or zero variance is flagged
- The pipeline runs for expansion-team players without error

## Stop

Show the feature summary and the leakage test result. Update `PROGRESS.md` and
`DECISIONS.md` with the chosen `k` values. Wait.
