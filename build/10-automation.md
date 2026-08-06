# Phase 10 — Automation

**Guide:** §14 (all of it), §15 for ongoing operation
**Prerequisite:** phase 9, **and the model must have beaten its baselines.**

**If phase 9 showed the model losing to baseline 3 or 4, say so and ask the user
whether they want to automate anyway.** An automated pipeline feeding a broken
model just produces wrong answers faster. It is still legitimate to automate data
collection alone — recommend that instead.

## Tier 1 — Double-clickable script

Build this first. A `.command` (Mac) or `.bat` (Windows) file that runs `update`
then `project` and leaves output visible. Explain exactly where to put it and how
to make it executable. Still manual, but one click, and it meaningfully increases
the odds the user actually runs it daily.

## Tier 2 — GitHub Actions

Free, no server, no credit card. **Explain the YAML line by line. Assume zero
knowledge.**

- Schedule multiple daily runs. Give the UTC cron for each Eastern time the user
  wants, and **remind them about daylight saving.**
- ⚠️ **Warn explicitly that scheduled workflows are routinely delayed 10–30
  minutes**, sometimes longer. Do not schedule a closing-line capture at T−5 and
  expect it to land. Help pick times that tolerate the delay.
- ⚠️ GitHub **disables scheduled workflows on repos with no activity for 60
  days.** A daily job that commits data counts as activity — but the user should
  know the rule.
- Store `ODDS_API_KEY` as a **GitHub Secret**. Show where in the UI. Never put it
  in the YAML.
- Commit the updated database back to the repo after each run. **This requires an
  exception in `.gitignore`, which currently excludes `*.db`** — make the change
  and record it in `DECISIONS.md`. Git warns past 50 MB and hard-limits at 100 MB;
  tell the user what to do when they approach it (guide §14.3).
- Configure email notification on failure.

## Tier 3 — VPS

Only mention if the user is bothered by Actions' timing imprecision, which they
should be if serious about closing-line capture. ~$5/month, `cron` or a `systemd`
timer, precise timing, and they now own a Linux box to keep patched.

## Monitoring

Automation without monitoring is worse than manual operation — it fails silently
and the user finds out three weeks later that the archive has a hole in it.

- Every run logs: timestamp, records fetched, errors, remaining API quota
- **Staleness check: if the newest odds snapshot is more than 36 hours old, fail
  the run loudly** rather than exiting quietly. This is the check that catches
  silent failures.
- Weekly summary: days run, days missed, quota consumed

## Backups

**Keep a backup of the odds archive you collect.** Historical odds may be
available from a provider, but coverage varies by plan, bookmaker, market, and
time period; do not assume an exact July 14 snapshot can be restored later.

- Weekly database dump plus raw JSON to a location separate from the runner
- Write `RESTORE.md` with exact rebuild steps
- **Make the user test the restore once.** An unverified backup is a hope.

## Manual availability override

Add `today_out.csv` that the user edits before running `project`, feeding the
phase 5 availability inputs. Ugly, works, takes two minutes a day. Automated
injury scraping comes later, if ever.

## Definition of done

- Double-clickable script works
- Actions workflow runs on schedule and commits successfully
- Failure notification tested by deliberately breaking a run
- Staleness check tested by faking an old snapshot
- Restore tested from backup

## Stop

Confirm each check. Update `PROGRESS.md`. Point the user to guide §15 for the
daily/weekly/monthly operating rhythm.
