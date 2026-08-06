# Phase 9 — Evaluation

**Guide:** §13 (all of it), §16 for what to check when results look too good
**Prerequisite:** phase 8

## Goal

Find out whether the model is any good, honestly.

**This is where the user may find out they wasted six weeks.** That is the point.
Be rigorous and do not soften anything.

## Validation structure

**Walk-forward only. Never a random split** — a random split trains on August and
predicts June, which is impossible and produces results that look wonderful and
mean nothing.

```
train through Jun 15 -> predict Jun 16-22
train through Jun 22 -> predict Jun 23-29
...
```

Accumulate out-of-sample predictions and evaluate them together.

**Freeze the final 3 weeks as an untouched holdout.** Do not evaluate on it, do
not tune on it. **Warn the user if they ask you to.** Every time it's looked at
and something changes in response, it becomes training data and the only unbiased
measurement is spent.

## Distributional metrics

- **CRPS** against realized values — overall, by market, by minutes bucket. The
  primary metric. Rewards accuracy and appropriate sharpness.
- **PIT histogram**, saved to `reports/`. **State in words what the shape means.**
  Flat = calibrated. U-shaped = too narrow, overconfident. Peaked = too wide.
  Sloped = systematic bias.
- **Interval coverage at 50/80/95%** — report all three.

## Binary metrics vs. the posted line

- Log loss, Brier score
- **Reliability diagram** saved to `reports/`. Bucket by predicted probability,
  plot predicted vs. observed. On the diagonal is calibrated. A model that says
  65% and hits 52% is not calibrated, and no amount of Kelly sizing fixes that.
  This matters more than accuracy — a calibrated model that's rarely confident is
  useful; an overconfident accurate model bankrupts you.

## Baselines — run all four, one table, side by side

1. Season-to-date average
2. Trailing-10 average
3. **Trailing-10 per-40 rate × projected minutes** — the real bar. Cheap, captures
   the core structural insight, and most models lose to it. If all the
   hierarchical modeling can't beat this, the hierarchical modeling isn't doing
   anything.
4. **The de-vigged market line as a probability** — the honest bar. If the model
   can't beat the market's own implied distribution out of sample, there's no
   edge. That's not a failure; most models don't, and knowing it is worth more
   than a bankroll graph.

**State plainly whether the model beats each. Do not soften a loss.**

## CLV

For every bet the model would have made, compare the price taken to the closing
price on that market. Report mean CLV in cents and percentage of bets with
positive CLV.

**If closing lines are unavailable, say so and skip it.** Do not substitute a
different price and call it closing.

Why this matters more than ROI: at −110, breakeven is 52.38%. Distinguishing a
genuine 55% win rate from 50% needs roughly a thousand bets for the point estimate
to even exclude coin-flipping, and several thousand for real power. At a handful
of qualifying bets per slate that's more than one full 44-game WNBA season,
probably two. The user will never have enough bets to separate skill from luck by
profit alone. CLV gives a usable signal in weeks.

## Do not produce

**Bankroll curves, ROI, units won, or any backtest against prices of unknown
capture time.** If the user asks, remind them the sample size cannot support it.

## If results look too good

Audit for leakage before celebrating. See `recovery.md` and guide §16. The most
common causes: a scaler fit outside the training fold, voided props counted as
unders, or a rolling window with `center=True`.

## Stop

Print the baseline comparison table, calibration plots, and CLV. Update
`PROGRESS.md` with a plain statement of whether the model beat baselines 3 and 4.
Wait.
