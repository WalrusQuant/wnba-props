# Phase 8 — Pricing

**Guide:** §12 (all of it)
**Prerequisite:** phase 7

## Goal

Turn a model probability and a market price into a decision.

## De-vigging

```
American odds -> implied probability
  negative:  p = (-odds) / (-odds + 100)
  positive:  p = 100 / (odds + 100)
```

At −115/−115 both sides imply 53.5%, summing to **107%**. That 7% is the hold.
Props routinely run 6–12%, versus roughly 4.5% on standard sides.

**Remove the vig before comparing anything.** A model saying 54% on a −115 side
is not finding a 0.5% edge over the 53.5% implied — the market's true estimate is
about 50%, and the edge is real but small. Without de-vigging, every calibration
statistic in phase 9 is wrong.

**Implement two methods, selectable in `config.yaml`:**

- **Multiplicative** — divide each raw implied probability by their sum. Simple,
  fine for balanced markets, known to under-price favorites on lopsided ones.
- **Power** — solve for exponent `k` where `q_over^k + q_under^k = 1`. Handles
  lopsided markets better. About four lines with `scipy.optimize.brentq`.

**Print both for every market.** On −115/−115 they agree to a fraction of a
percent; on −250/+190 they diverge meaningfully. If results are sensitive to the
choice, that's informative in itself.

## Fair price vs. best price

Distinguish these clearly — conflating them is costly in both directions:

- **Fair probability** — from a sharp book, or a de-vigged consensus of several.
  This is the market's estimate.
- **Best available price** — what the user could actually bet.

```
edge = model_p_over - fair_p_over
EV   = computed against the best available price
```

## Sizing

```
f* = (p × b - (1 - p)) / b        b = decimal odds - 1
```

**Fractional Kelly, default 0.25.** Full Kelly assumes the probability estimate is
correct; it isn't, and Kelly is extremely punishing when `p` is overestimated —
which every new modeler does. Print both full and fractional so the difference is
visible.

**Minimum edge floor, default 3%.** A computed 0.4% edge is noise; the difference
between 0.4% and 0% is far smaller than model error. Tune on validation data.

## Output

CSV of today's slate sorted by edge: player, market, line, best price, book, model
P(over), fair P(over), edge, quarter-Kelly stake.

## Do not build

**No bankroll graph. No profit projection. No ROI.** Phase 9 has not established
that the model works. If the user asks, say the sample size cannot support it.

## Definition of done

- Hold printed per two-way market
- Both de-vig methods printed side by side
- Fair and best price clearly distinguished in output
- Slate CSV generated

## Stop

Show the slate CSV and the hold figures. Update `PROGRESS.md`. Wait.
