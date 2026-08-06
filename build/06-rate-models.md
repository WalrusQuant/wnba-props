# Phase 6 — Rate models

**Guide:** §10 (all of it)
**Prerequisite:** phase 5

## Goal

Distributions over production per unit of playing time.

**Build one stat completely before starting the next.** Order: three-pointers
made, rebounds, assists, points.

## Distribution choice

**3PM — start here, it's the cleanest.**

```
3PM ~ Binomial(3PA, p3)
```

Model attempts and accuracy separately. `3PA` is a count per-40, scaled by the
minutes draw. `p3` comes from a Beta prior shrunk toward role and league average —
small-sample three-point percentage is notoriously unstable, and a player who is
6-for-12 has not shown you 50%.

**Rebounds and assists — negative binomial, NOT Poisson.**

The default instinct is Poisson and it is wrong here in a direction that hurts:
Poisson forces variance = mean, but real rebound and assist counts are
**overdispersed**. Using Poisson gives distributions that are too narrow, which
overstates confidence and makes low lines look like automatic overs.

**First compute and print the observed variance-to-mean ratio** in the data to
justify the choice. If it's near 1, say so and reconsider.

**Points — do not model directly.**

```
PTS = 2 × 2PM + 3 × 3PM + FTM
```

Model the components and sum them in simulation. This produces the correct lumpy,
multi-modal shape a smooth continuous distribution cannot, and improvements to the
3PM model propagate to points for free.

**Combos (PRA, P+R, R+A) — never fit the sum.** They fall out of phase 7's
simulation with their correlations intact. Fitting the sum directly throws away
that structure and gets the tails wrong, which is exactly where the money is.

## Hierarchical structure

```
league average -> role/position average -> player estimate
```

Each level shrinks toward the one above, by how much data the player has. A rookie
in game 8 is pulled hard toward the role prior; a veteran in game 40 mostly stands
alone.

**Start with empirical-Bayes shrinkage, not full MCMC.** Get the whole pipeline
working end to end, then upgrade the component that most needs it. PyMC or numpyro
give honest posteriors but are slower to fit and much harder to debug.

Print effective sample size and shrinkage weight per player.

## Opponent adjustments

**Team level only.** With 15 teams and 44 games, a player has faced any opponent a
handful of times. Team-level effects (this team allows more threes) are estimable;
player-vs-team effects are almost never estimable at this sample size, however
tempting the narrative. If you think an interaction is justified, **state the
sample size supporting it first.**

## Definition of done

Per stat, on held-out games, before adding the next:

- CRPS against realized values
- **PIT histogram.** Flat means calibrated. U-shaped means distributions too
  narrow (overconfident — usually Poisson where you needed NB, or minutes variance
  too low). Peaked means too wide. Sloped means systematic bias. State in words
  what the shape shows.
- Comparison against baselines: season-to-date rate, trailing-10 rate

## Stop

After each stat, print its metrics. Update `PROGRESS.md` noting which stats are
complete. Wait.
