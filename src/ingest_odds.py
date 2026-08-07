"""Builds a growing, timestamped archive of WNBA player-prop lines in
odds_snapshots from The Odds API's per-event odds endpoint.

Every snapshot is inserted, never updated in place -- this is a time series
and its value is in the movement. `--dry-run` re-parses the most recently
saved raw response instead of calling the API, so the parser can be
developed without spending credits.
"""

import json
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from src.config import load_config
from src.db import get_connection
from src.log import get_logger
from src.odds_client import OddsApiError, Quota, fetch_event_odds, fetch_events, latest_raw_files

log = get_logger(__name__)

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
US_EASTERN = ZoneInfo("America/New_York")


def _load_api_key() -> str | None:
    load_dotenv(ENV_PATH)
    key = os.environ.get("ODDS_API_KEY")
    return key if key else None


def _today_et() -> str:
    return datetime.now(US_EASTERN).strftime("%Y-%m-%d")


def _parse_event_odds(
    event_data: dict, captured_at: str, markets: list[str]
) -> list[tuple]:
    """Flattens one event-odds response into odds_snapshots rows. A player
    prop market's outcomes come in Over/Under pairs sharing a player name and
    line; this pairs them back into one row per (book, market, player, line)."""
    rows = []
    game_id = str(event_data.get("id", ""))
    commence_time = event_data.get("commence_time")
    home_team = event_data.get("home_team")
    away_team = event_data.get("away_team")

    bookmakers = event_data.get("bookmakers") or []
    for bm in bookmakers:
        book = bm.get("key", "unknown")
        for mkt in bm.get("markets") or []:
            market_key = mkt.get("key", "unknown")
            is_alternate = 1 if market_key.endswith("_alternate") else 0
            base_market = market_key[: -len("_alternate")] if is_alternate else market_key
            if base_market not in markets:
                continue

            pairs: dict[tuple, dict] = {}
            for outcome in mkt.get("outcomes") or []:
                player = outcome.get("description")
                line = outcome.get("point")
                side = outcome.get("name")
                price = outcome.get("price")
                if player is None or side not in ("Over", "Under"):
                    continue
                key = (player, line)
                pairs.setdefault(key, {})[side] = price

            for (player, line), sides in pairs.items():
                rows.append(
                    (
                        captured_at, game_id, commence_time, home_team, away_team,
                        book, market_key, player, line,
                        sides.get("Over"), sides.get("Under"), is_alternate,
                    )
                )
    return rows


def _insert_rows(conn: sqlite3.Connection, rows: list[tuple]) -> int:
    before = conn.total_changes
    conn.executemany(
        """
        INSERT INTO odds_snapshots (
            captured_at_utc, game_id, commence_time_utc, home_team_raw, away_team_raw,
            book, market, player_name_raw, line, over_price, under_price, is_alternate
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT DO NOTHING
        """,
        rows,
    )
    return conn.total_changes - before


def _print_quota(quota: Quota | None, markets: list[str], regions: list[str], odds_cfg: dict, conn: sqlite3.Connection) -> None:
    log.info("")
    log.info("=== Quota ===")
    if quota is None or quota.remaining is None:
        log.info("no quota data (dry-run: no network call was made)")
        return
    log.info("remaining: %s, used this account: %s, cost of last call: %s", quota.remaining, quota.used, quota.last_cost)

    cost_per_call = len(markets) * len(regions)
    row = conn.execute(
        "SELECT MIN(game_date), MAX(game_date), COUNT(*) FROM ("
        "SELECT DISTINCT game_id, game_date FROM scheduled_games "
        "WHERE season = (SELECT MAX(season) FROM scheduled_games) AND game_date IS NOT NULL)"
    ).fetchone()
    min_date, max_date, n_games = row
    avg_games_per_day = None
    if min_date and max_date and n_games:
        days = (datetime.fromisoformat(max_date) - datetime.fromisoformat(min_date)).days + 1
        if days > 0:
            avg_games_per_day = n_games / days

    if avg_games_per_day is None:
        log.info("projected monthly usage: unavailable (no scheduled_games data -- run `python run.py update` first)")
        return

    snapshots_per_day = odds_cfg["snapshots_per_day"]
    projected_monthly = cost_per_call * avg_games_per_day * snapshots_per_day * 30
    log.info(
        "credit cost per game call: %d (markets=%d x regions=%d)",
        cost_per_call, len(markets), len(regions),
    )
    log.info(
        "season average: %.1f games/day (%d scheduled games over %d days)",
        avg_games_per_day, n_games, days,
    )
    log.info(
        "projected monthly usage at %d snapshots/day: ~%.0f credits/month",
        snapshots_per_day, projected_monthly,
    )


def run_odds_update(dry_run: bool = False) -> None:
    config = load_config()
    odds_cfg = config["odds"]
    sport_key = odds_cfg["sport_key"]
    markets = odds_cfg["markets"]
    regions = odds_cfg["regions"]
    price_format = odds_cfg["price_format"]

    conn = get_connection()

    if dry_run:
        _run_dry(conn, markets)
        conn.close()
        return

    api_key = _load_api_key()
    if not api_key:
        log.info(
            "no ODDS_API_KEY found -- copy .env.example to .env, add your key from "
            "the-odds-api.com (with hyphens), and re-run `python run.py update`. Skipping odds ingestion."
        )
        conn.close()
        return

    before = conn.execute("SELECT COUNT(*) FROM odds_snapshots").fetchone()[0]
    last_quota = None
    today = _today_et()
    games_seen = games_with_props = rows_inserted = 0

    try:
        events, last_quota, captured_at = fetch_events(api_key, sport_key)
    except OddsApiError as e:
        log.info("could not list events: %s -- exiting cleanly", e)
        conn.close()
        return

    todays_events = [e for e in events if _et_date(e.get("commence_time")) == today]

    if not todays_events:
        log.info("no games today (%s ET) -- nothing to snapshot", today)
    else:
        log.info("today's slate: %d game(s)", len(todays_events))

    for event in todays_events:
        event_id = event.get("id")
        games_seen += 1
        try:
            data, quota, captured_at = fetch_event_odds(api_key, sport_key, event_id, markets, regions, price_format)
            last_quota = quota
        except OddsApiError as e:
            log.info("  event %s: HTTP/network error, skipping: %s", event_id, e)
            continue

        try:
            rows = _parse_event_odds(data, captured_at, markets)
        except (KeyError, TypeError) as e:
            log.info("  event %s: malformed response, skipping: %s", event_id, e)
            continue

        if not rows:
            log.info("  event %s (%s @ %s): no props posted yet", event_id, event.get("away_team"), event.get("home_team"))
            continue

        games_with_props += 1
        n = _insert_rows(conn, rows)
        rows_inserted += n
        conn.commit()
        log.info("  event %s (%s @ %s): %d row(s)", event_id, event.get("away_team"), event.get("home_team"), n)

    after = conn.execute("SELECT COUNT(*) FROM odds_snapshots").fetchone()[0]
    log.info("")
    log.info("=== Odds snapshot summary ===")
    log.info("games seen: %d, games with props posted: %d", games_seen, games_with_props)
    log.info("rows inserted: %d (odds_snapshots total: %d -> %d)", rows_inserted, before, after)

    _print_quota(last_quota, markets, regions, odds_cfg, conn)
    conn.close()


def _et_date(commence_time: str | None) -> str | None:
    if not commence_time:
        return None
    try:
        dt = datetime.fromisoformat(commence_time.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.astimezone(US_EASTERN).strftime("%Y-%m-%d")


def _run_dry(conn: sqlite3.Connection, markets: list[str]) -> None:
    files = latest_raw_files()
    if not files:
        log.info(
            "no raw odds files found under data/raw/odds/ -- run `python run.py update` "
            "at least once (with ODDS_API_KEY set) before using --dry-run"
        )
        return

    log.info("--dry-run: re-parsing %d raw file(s) from the most recent capture, no network call", len(files))

    before = conn.execute("SELECT COUNT(*) FROM odds_snapshots").fetchone()[0]
    rows_would_insert = 0
    for path in files:
        if "__events" in path.name:
            continue
        captured_at = path.name.split("__")[0]
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        try:
            rows = _parse_event_odds(data, captured_at, markets)
        except (KeyError, TypeError) as e:
            log.info("  %s: malformed, skipping: %s", path.name, e)
            continue
        n = _insert_rows(conn, rows)
        rows_would_insert += n
        conn.commit()
        log.info("  %s: %d row(s)", path.name, n)

    after = conn.execute("SELECT COUNT(*) FROM odds_snapshots").fetchone()[0]
    log.info("")
    log.info("=== Odds snapshot summary (dry-run) ===")
    log.info("rows inserted: %d (odds_snapshots total: %d -> %d)", rows_would_insert, before, after)
    _print_quota(None, markets, [], {"snapshots_per_day": 0}, conn)
