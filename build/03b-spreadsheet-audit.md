# Optional — Audit a hand-kept prop log

**Guide:** §6.6
**Run before phase 3, only if the user has been tracking props in a spreadsheet.**

## Goal

Establish what is actually in the user's file and what it can support. **You have
not seen this file. Assume nothing about its structure.**

Do not write modeling code in this phase.

## Step 1 — Inventory, no interpretation

- Load every sheet. For each print: sheet name, dimensions, the header row if you
  can identify one, and the first 20 and last 20 rows **verbatim**.
- For every column: header text, inferred type, null count, distinct count, and 10
  sample values. Do not rename or coerce anything.
- Flag merged cells, multiple tables on one sheet, blank separator rows, totals
  rows, and formatting-as-data (color coding, strikethrough).

**Stop and show the user this before proceeding.**

## Step 2 — Classify

For each of the following, say **"present"** or **"not present."** Do not derive,
infer, or guess:

one row per prop vs. aggregated · player identifier · date · market type · the
line · price/odds and which side · sportsbook · capture time · side taken ·
outcome or realized stat · stake or units

## Step 3 — State what this log can and cannot support

Reason from what is present, not what would be convenient:

- **If it only contains props the user bet**, it is a record of their behavior,
  not a sample of the market. It cannot measure market efficiency or estimate how
  often the model finds edges. Say this plainly.
- **If prices are missing**, nothing expected-value related can be computed.
  Line-only data supports "which side was correct" and nothing more.
- **If outcomes are missing**, they can be derived later by joining to
  `player_games`. Do not fabricate them now.
- **If capture time is missing or inconsistent**, these are not closing lines and
  cannot support CLV in phase 9.
- **Report field completeness by month, not overall.** Tracking habits change
  over a season.

Report usable observations **per player-market pair**, not just total rows. Eight
thousand rows across five markets and 150 players is ten per cell, which supports
very little.

Write everything to `reports/log_audit.md`.

## Step 4 — Ask

List everything you could not determine from the file itself as direct questions.
**Wait for answers.** Then propose a normalized schema and cleaning plan for
approval. Clean nothing silently. Keep a column linking every cleaned row back to
its original spreadsheet row.

## Stop

Show `reports/log_audit.md`. Ask the open questions. Wait.
