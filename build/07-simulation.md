# Phase 7 — Simulation

**Guide:** §11 (all of it)
**Prerequisite:** phase 6

## Goal

A joint distribution over every stat for every player in a game.

## Why simulate rather than compute

1. **Combo props** need the joint distribution, not three marginals
2. **Uncertainty propagation** — minutes uncertainty must flow into stat
   uncertainty. Multiplying a minutes point-estimate by a rate point-estimate
   discards the variance that matters most.
3. **Correlation** — minutes are zero-sum within a team, shots are partly
   zero-sum, and game pace lifts everyone together

## Structure

Per game, N simulations:

```
1. sample pace -> total possessions per team
2. sample the Dirichlet minutes-share vector -> player minutes summing to 200
3. per player:
     sample usage share, conditional on who's on the floor
     shot attempts from minutes × pace × usage
     makes from attempts × shooting rates
     rebounds and assists from per-40 rates × that simulation's minutes
4. derive points from 2PM/3PM/FTM, and all combos, per simulation
```

Then every prop question is a counting operation:

```
P(points >= 19) = (sims where points >= 19) / N
```

Combos, alternate lines, and correlated same-game questions all come free.

## Parameters

- **N = 10,000** for main lines; **50,000** if tails matter (deep alternates,
  milestone markets). Configurable.
- **Set and store a random seed.** Reproducibility matters when debugging why
  yesterday's number differed.
- **Vectorize with numpy** across the whole slate. Python loops over 50,000 sims ×
  12 players × 7 games will be slow enough to discourage iteration.
- **Store the summary, not the draws** — percentiles at 1-unit intervals plus mean
  and sd.

## Sanity checks, printed every run

- Team minutes sum to 200 in regulation; add 25 only after an explicit simulated
  overtime event
- Simulated team points against the posted game total, if available
- Simulated team rebounds land in a realistic range, not double it
- **For 5 players the user names, overlay the simulated distribution against that
  player's actual season game log** and save to `reports/`

That last check is the best debugging tool in the project. If the simulation says
a player scores 25+ in 30% of games and she's done it twice in 40, something is
wrong.

## Definition of done

- All sanity checks pass
- Overlay plots saved and shown to the user
- `P(stat >= k)` output for a range of k around each posted line

## Stop

Show the overlay plots. Update `PROGRESS.md`. Wait.
