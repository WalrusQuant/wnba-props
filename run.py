"""Single entry point for the WNBA prop model: python run.py <subcommand>.

Each subcommand is implemented in the phase that needs it; until then it
prints a not-implemented message and exits cleanly instead of stubbing logic.
"""

import argparse
import sys

from src.log import get_logger

log = get_logger(__name__)

# Command -> phase that implements it, for the not-implemented message.
NOT_IMPLEMENTED = {
    "clean": 3,
    "train": 5,
    "project": 7,
    "evaluate": 9,
    "audit": 3,
}


def _not_implemented(command: str) -> None:
    phase = NOT_IMPLEMENTED[command]
    log.info("not implemented — phase %d builds this", phase)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run.py",
        description="WNBA player prop projection model.",
    )
    subparsers = parser.add_subparsers(dest="command")

    update_parser = subparsers.add_parser("update", help="fetch new games and odds since last run")
    update_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="re-parse the most recently saved raw odds response instead of calling the API",
    )
    subparsers.add_parser("clean", help="rebuild clean tables from raw")
    subparsers.add_parser("train", help="fit models, save to disk")
    subparsers.add_parser("project", help="today's slate -> console + CSV")
    subparsers.add_parser("evaluate", help="calibration and scoring on holdout")
    subparsers.add_parser("audit", help="data quality report")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return 0

    if args.command == "update":
        from src.ingest_odds import run_odds_update
        from src.ingest_stats import run_update

        if not args.dry_run:
            run_update()
        run_odds_update(dry_run=args.dry_run)
        return 0

    _not_implemented(args.command)
    return 0


if __name__ == "__main__":
    sys.exit(main())
