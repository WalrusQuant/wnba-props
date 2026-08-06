# Phase 5 — Minutes model

**Guide:** §9 (all of it)
**Prerequisite:** phase 4

## Goal

A probability distribution over minutes played, for every player who might play
tonight.

**This is the most important model in the project.** Uncertainty in playing time
contributes more error than uncertainty in rate. Beginners spend 90% of their
effort on shooting rates and 10% on minutes; that's backwards. Get this right and
mediocre rate models still produce decent props.

## Build

**Two stages.** Minutes have a spike at zero and a continuous distribution above
it. One model handles neither well.

```
P(minutes = 0)      -> classifier
P(minutes | plays)  -> continuous on (0, 40]
```

In simulation, draw the coin flip first, then the minutes.

**Model minutes SHARE, not raw minutes.** Team minutes must total exactly 200 —
WNBA games are 40 minutes, not 48: 200 team-minutes in regulation. This constraint
is free information and naive models throw it away, producing rosters that sum to
214. If pricing props that include overtime, simulate a game-level overtime event
first, then add 25 team-minutes for each simulated overtime period.

```
per team-game:
  sample a share vector over active players from a Dirichlet
  minutes_i = share_i × 200
```

Fit the Dirichlet's concentration from historical rotations conditioned on
availability. This guarantees the constraint in every simulation and naturally
produces the correlation you want — when one player comes in high, someone else
comes in low.

If the Dirichlet is too much machinery for a first pass, model players
independently and normalize the team's draws to 200. Cruder, distorts the tails,
but a legitimate starting point. Record which you chose in `DECISIONS.md`.

**Do not use per-36 anywhere.** Grep for `36` before you finish.

## Conditioning variables

In rough order of importance:

1. Trailing 3–5 game minutes, weighted recent
2. **Who else is available** — dominant when a rotation player is out
3. Started flag
4. **Game script** — blowouts collapse starter minutes. If the game spread is
   available, use it directly as a blowout proxy: a player on a heavy favorite has
   a **fatter left tail** than the same player in a close game. This correlation
   is real and material, and it's a reason to simulate rather than multiply point
   estimates.
5. Rest days, back-to-back
6. Injury return — minutes restrictions are announced by beat reporters and cannot
   be inferred from data

## Availability at projection time

Historical box scores are easy; knowing who plays *tonight* is hard and is most of
the value. For now, build on historical availability so you can develop and
evaluate. **Be explicit in the output that the backtest knows who played** — the
gap between "knew the lineup" and "didn't" is large and is the difference between
a real result and a fantasy. Phase 10 adds a manual `today_out.csv` override.

## Definition of done

- MAE of the median prediction
- **Coverage of 50/80/95% intervals — report all three.** Calibrated at 50% but
  not 95% means tail problems, and props live in the tails.
- Log loss and calibration plot for the DNP classifier
- A test asserting simulated team minutes sum to 200 in regulation; add 25 only
  after an explicit simulated overtime event
- **Side-by-side comparison against two baselines:** trailing-5-game mean minutes,
  and last game's minutes

**If the model does not beat trailing-5 on both MAE and coverage, say so plainly
and stop.** Do not proceed to phase 6, do not suggest the metric is unfair.

## Stop

Print the comparison table and coverage figures. Update `PROGRESS.md`. Wait.
