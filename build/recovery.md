# Recovery

For when something breaks or looks wrong. Not part of the phase sequence.

**General rule: the answer is almost always in the data layer, not the model.**
Check the join rate first, then the source schema, then the model.

---

## The backtest looks too good

Treat this as a bug report, not a result. Audit in this order and report findings
without softening:

1. **Scalers, imputers, encoders fit outside the training fold** — the most common
   and most invisible leak. It leaks the future's *distribution* into the past.
2. **Voided props counted as unders** — a scratched player has props voided. If
   they're treated as outcomes, unders look wildly profitable. Check the void flag
   from phase 3 is being applied.
3. **`center=True` rolling windows** — grep for it.
4. **Season aggregates including future games** — team pace, opponent defensive
   rating, season averages.
5. **Random rather than time-based split.**
6. **Backtest prices with unknown capture time** — if `captured_at_utc` is null or
   inconsistent, the result is uninterpretable regardless of everything else.
7. **Stale lines that weren't really available** — an edge at a book that would
   have limited the user, or a price that existed for 40 seconds. Real edges at
   real limits are much smaller than backtested ones.

Run the as-of feature test from phase 4. If it doesn't exist, that's the answer.

---

## Match rate dropped

Diff this week's unmatched names against last week's. Check:

- A book changed its name formatting
- New players entered the league (trades, signings, injury replacements)
- The stats source changed its schema
- A team's players aren't in `name_map` — check expansion teams specifically

Show the specific rows. Do not fuzzy-match your way past it.

---

## Ingestion produces nulls where it used to produce values

**Do not re-fetch.** Re-parse the raw JSON in `data/raw/` and diff the schema
between a working date and a broken one. Report exactly which field changed. This
is why raw responses are saved.

---

## Team minutes don't sum to 200

A parsing bug, not a model bug. A player was dropped from the box score, or
overtime periods aren't being counted (each adds 25). Find the specific game.

---

## PIT histogram is U-shaped

Distributions are too narrow — the model is overconfident. Usual causes:

- Poisson where negative binomial was needed. Check the variance-to-mean ratio.
- Minutes variance too low. Check phase 5's interval coverage first; if minutes
  aren't calibrated, nothing downstream can be.
- Shrinkage `k` too small, so player estimates are chasing noise.

---

## The model tracks whichever side ran hot recently

"Unders were printing in June, overs since July" is not a discovered regime — it's
noise in a market that reprices continuously. If one side were genuinely mispriced
for two months, the line would have moved.

A model whose evaluation output follows the recent hot side is leaking or
overfitting. Check shrinkage weights and the as-of test.

---

## API quota exhausted

Check idempotency first — a job re-fetching everything nightly is the usual cause.
Then check snapshot cadence against the projection printed in phase 2. Reduce
markets before reducing snapshot frequency; the closing-line capture is the one
that matters.

---

## Automated runs stopped silently

- GitHub disables scheduled workflows after 60 days of repo inactivity
- Check whether failure notification was ever configured
- Check the staleness alert from phase 10 fired and was missed
- Gaps in the odds archive may be fillable from a historical provider, but exact
  coverage depends on plan, bookmaker, market, and timestamp. Note the affected dates
  in `DECISIONS.md` so phase 9's evaluation accounts for them.
