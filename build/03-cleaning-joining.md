# Phase 3 — Cleaning and joining

**Guide:** §7 (all of it)
**Prerequisite:** phases 1 and 2. Run `03b-spreadsheet-audit.md` first if the user
has a hand-kept log.

## Goal

One trustworthy table where every prop line sits next to its actual result, and
the user knows exactly how many rows were lost and why.

**This phase is boring and it is where projects die.** A failed join drops rows
silently and the model trains happily on whatever matched.

## Build

**The join.** `odds_snapshots` → `player_games` on player identity and
Eastern-time game date.

**Name matching.** Books and stats providers do not agree on spelling. Build an
explicit `name_map` crosswalk (`raw_name, source, player_id, confidence,
mapped_by`) using this cascade:

1. Exact match after light normalization — unicode NFKD, strip punctuation,
   collapse whitespace, lowercase
2. Match within team and date — a book's `K. Plum` on an Aces night is unambiguous
3. Fuzzy matching to **propose** candidates, printed for user approval

**Never auto-accept a fuzzy match.** Persist every approval so each name is
approved exactly once, ever.

Expect: curly vs. straight apostrophes, `Lastname, Firstname` ordering, suffixes,
hyphens, accented characters, and occasionally two players sharing a surname.

**Timezones.** Games are scheduled US Eastern; APIs return UTC. A 10 PM Pacific
tip is already the next calendar day in UTC, so a naive conversion silently
attaches West Coast games to the wrong date. Store UTC with explicit timezone
info, derive `game_date_et`, and join on that. Never do date arithmetic on
strings. The league now spans four time zones plus an international border.

**Flag explicitly, one column each:**

- **Whole-number lines** — a line of 15 (not 15.5) can push
- **Alternate/ladder lines** — mixing these into the main series corrupts your
  sense of the market's estimate
- **Voided props** — a scratched player's props are voided. These have a line and
  no result. **They are not unders.** Treated carelessly, a scratched star with a
  21.5 line becomes an under that "hit," and unders start looking wildly
  profitable. This is a catastrophic and common bug.

**Multiple books.** Do not average simultaneous lines into a consensus and discard
the spread. The disagreement is signal.

## The unmatched report — non-negotiable

Every clean run writes `reports/unmatched.md`:

- Every odds row with no matching player-game, with raw name and date
- Every player-game with no odds row (expected — not everyone gets props)
- Match rate overall, **by book, by month, and by team**
- Top 20 unmatched names by frequency

Tell the user to read it weekly. A match rate dropping from 96% to 71% in July
means something changed, and this report is the only place it shows up.

## Definition of done

- `reports/unmatched.md` exists and the user can read it and understand the loss
- Before/after row counts printed at every step, with reasons for any drop
- Voided props are flagged and excluded from outcome data
- Nothing is dropped silently — unmatched rows persist with a reason code

## Stop

Show the unmatched report and the match rate. Update `PROGRESS.md`. Wait.
