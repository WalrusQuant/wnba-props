# Phase 0 — Environment and scaffold

**Guide:** §3, §4
**Prerequisite:** none

## Goal

A working Python environment, a `run.py` that does nothing yet but does it
correctly, and a `config.yaml`. Nothing that touches a network.

## Build

- Initialize `pyproject.toml` with `uv`. Python 3.11+. Start with no dependencies
  beyond what you need for the CLI itself.
- Create `run.py` as the single entry point with argparse subcommands: `update`,
  `clean`, `train`, `project`, `evaluate`, `audit`. Every one of them currently
  prints "not implemented — phase N builds this" and exits cleanly. Do not stub
  logic; stub the interface only.
- Create `config.yaml` with a `season: 2026` key and nothing else yet. Phases add
  to it as they need values.
- Set up logging: plain text to `logs/`, plus readable console output. One helper
  the whole project uses, not a logger per module.
- Confirm `.gitignore` and `.env.example` exist and are correct.
- Tell the user the exact commands to install `uv` on their OS, and to copy
  `.env.example` to `.env`.

## Definition of done

- `python run.py --help` lists all six subcommands
- `python run.py update` prints the not-implemented message and exits 0
- `python run.py` with no arguments prints help, not a traceback
- `uv sync` works from a clean checkout

## Stop

Print the command list. Update `PROGRESS.md`. Wait.
