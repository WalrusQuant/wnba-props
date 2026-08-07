"""Builds games, player_games, availability, players, and teams in data/wnba.db
from sportsdataverse-data's WNBA schedule and box score snapshots.

Historical seasons (everything before the current config season) are treated
as immutable once ingested and are skipped on later runs; the current season
is always re-checked so in-progress results get picked up.
"""

import sqlite3
from collections import Counter

from src.config import load_config
from src.db import get_connection
from src.log import get_logger
from src.sdv_fetch import fetch_season

log = get_logger(__name__)

# ESPN tags the WNBA All-Star draft squads as fake "teams" with this naming
# convention (e.g. "TEAM COOP", "TEAM SPOON"). They show up in the schedule
# and box scores like a real game but aren't a franchise, so they're excluded
# from every table this phase builds.
EXHIBITION_PREFIX = "TEAM "

DNP_COACH_REASONS = {"COACH'S DECISION", "DID NOT DRESS"}
DNP_REST_REASONS = {"REST", "RETURN TO COMPETITION RECONDITIONING"}
INACTIVE_REASONS = {"NOT WITH TEAM", "PERSONAL", "SUSPENDED BY LEAGUE"}


def classify_status(did_not_play: bool, reason: str | None) -> str:
    """Maps ESPN's free-text DNP reason to the project's fixed status enum."""
    if not did_not_play:
        return "played"
    r = (reason or "").strip().upper()
    if r in DNP_COACH_REASONS:
        return "dnp_coach"
    if r in DNP_REST_REASONS:
        return "dnp_rest"
    if r in INACTIVE_REASONS or r == "":
        return "inactive"
    return "dnp_injury"


def _is_exhibition(display_name: str | None) -> bool:
    return bool(display_name) and display_name.startswith(EXHIBITION_PREFIX)


def _get_meta(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM ingest_meta WHERE key = ?", (key,)).fetchone()
    return row[0] if row else None


def _set_meta(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO ingest_meta (key, value) VALUES (?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, value),
    )


def _backfilled_seasons(conn: sqlite3.Connection) -> set[int]:
    raw = _get_meta(conn, "seasons_backfilled")
    if not raw:
        return set()
    return {int(s) for s in raw.split(",") if s}


def _mark_backfilled(conn: sqlite3.Connection, seasons: set[int]) -> None:
    existing = _backfilled_seasons(conn)
    combined = existing | seasons
    _set_meta(conn, "seasons_backfilled", ",".join(str(s) for s in sorted(combined)))


def _upsert_team(conn: sqlite3.Connection, team_id: int, location, name, display_name, abbr, color, alt_color) -> None:
    conn.execute(
        """
        INSERT INTO teams (team_id, location, name, display_name, abbreviation, color, alternate_color)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(team_id) DO UPDATE SET
            location = excluded.location, name = excluded.name,
            display_name = excluded.display_name, abbreviation = excluded.abbreviation,
            color = excluded.color, alternate_color = excluded.alternate_color
        """,
        (team_id, location, name, display_name, abbr, color, alt_color),
    )


def _upsert_player(conn: sqlite3.Connection, player_id: int, name: str, position, season: int) -> None:
    row = conn.execute(
        "SELECT first_season, last_season FROM players WHERE player_id = ?", (player_id,)
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO players (player_id, player_name, position, first_season, last_season) "
            "VALUES (?, ?, ?, ?, ?)",
            (player_id, name, position, season, season),
        )
    else:
        first_season, last_season = row
        conn.execute(
            "UPDATE players SET player_name = ?, position = COALESCE(?, position), "
            "first_season = ?, last_season = ? WHERE player_id = ?",
            (name, position, min(first_season, season), max(last_season, season), player_id),
        )


def _team_possessions(fga, oreb, tov, fta, coef: float) -> float | None:
    if fga is None or oreb is None or tov is None or fta is None:
        return None
    return fga - oreb + tov + coef * fta


def _ingest_season(conn: sqlite3.Connection, season: int, coef: float) -> dict:
    """Fetches one season and upserts it into every table. Returns row counts fetched."""
    schedule = fetch_season("schedule", season)
    player_box = fetch_season("player_box", season) or []
    team_box = fetch_season("team_box", season) or []

    if schedule is None:
        log.info("season %d: no schedule asset published, skipping", season)
        return {"games": 0, "player_games": 0}

    team_box_by_game = {}
    for row in team_box:
        team_box_by_game.setdefault(row["game_id"], {})[row["team_id"]] = row

    player_box_by_game = {}
    for row in player_box:
        player_box_by_game.setdefault(row["game_id"], []).append(row)

    non_exhibition = [
        r
        for r in schedule
        if not _is_exhibition(r.get("home_display_name"))
        and not _is_exhibition(r.get("away_display_name"))
    ]
    completed = [r for r in non_exhibition if r.get("status_type_completed")]

    for r in non_exhibition:
        _upsert_team(
            conn, r["home_id"], r.get("home_location"), r.get("home_name"),
            r.get("home_display_name"), r.get("home_abbreviation"),
            r.get("home_color"), r.get("home_alternate_color"),
        )
        _upsert_team(
            conn, r["away_id"], r.get("away_location"), r.get("away_name"),
            r.get("away_display_name"), r.get("away_abbreviation"),
            r.get("away_color"), r.get("away_alternate_color"),
        )
        conn.execute(
            "INSERT INTO scheduled_games (game_id, season, team_id, game_date) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(game_id, team_id) DO UPDATE SET game_date = excluded.game_date",
            (r["id"], season, r["home_id"], str(r.get("game_date"))),
        )
        conn.execute(
            "INSERT INTO scheduled_games (game_id, season, team_id, game_date) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(game_id, team_id) DO UPDATE SET game_date = excluded.game_date",
            (r["id"], season, r["away_id"], str(r.get("game_date"))),
        )

    for r in completed:
        game_id = r["id"]
        overtime_periods = max(0, int((r.get("status_period") or 4) - 4))
        game_minutes = 40 + 5 * overtime_periods

        tb = team_box_by_game.get(game_id, {})
        home_tb, away_tb = tb.get(r["home_id"]), tb.get(r["away_id"])
        home_poss = away_poss = None
        if home_tb:
            home_poss = _team_possessions(
                home_tb.get("field_goals_attempted"), home_tb.get("offensive_rebounds"),
                home_tb.get("total_turnovers"), home_tb.get("free_throws_attempted"), coef,
            )
        if away_tb:
            away_poss = _team_possessions(
                away_tb.get("field_goals_attempted"), away_tb.get("offensive_rebounds"),
                away_tb.get("total_turnovers"), away_tb.get("free_throws_attempted"), coef,
            )

        possessions_est = pace = home_off_rating = away_off_rating = None
        if home_poss is not None and away_poss is not None:
            possessions_est = (home_poss + away_poss) / 2
            pace = possessions_est * 40 / game_minutes
            if home_poss:
                home_off_rating = r["home_score"] / home_poss * 100
            if away_poss:
                away_off_rating = r["away_score"] / away_poss * 100

        conn.execute(
            """
            INSERT INTO games (game_id, season, game_date, home_team_id, away_team_id,
                home_score, away_score, overtime_periods, possessions_est, pace,
                home_off_rating, away_off_rating, attendance)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(game_id) DO UPDATE SET
                season = excluded.season, game_date = excluded.game_date,
                home_team_id = excluded.home_team_id, away_team_id = excluded.away_team_id,
                home_score = excluded.home_score, away_score = excluded.away_score,
                overtime_periods = excluded.overtime_periods,
                possessions_est = excluded.possessions_est, pace = excluded.pace,
                home_off_rating = excluded.home_off_rating, away_off_rating = excluded.away_off_rating,
                attendance = excluded.attendance
            """,
            (
                game_id, season, str(r["game_date"]), r["home_id"], r["away_id"],
                r.get("home_score"), r.get("away_score"), overtime_periods,
                possessions_est, pace, home_off_rating, away_off_rating,
                int(r["attendance"]) if r.get("attendance") else None,
            ),
        )

        for pr in player_box_by_game.get(game_id, []):
            if _is_exhibition(pr.get("team_display_name")):
                continue
            _upsert_player(
                conn, pr["athlete_id"], pr.get("athlete_display_name"),
                pr.get("athlete_position_name"), season,
            )
            plus_minus = pr.get("plus_minus")
            try:
                plus_minus = float(plus_minus) if plus_minus not in (None, "") else None
            except (TypeError, ValueError):
                plus_minus = None

            did_not_play = bool(pr.get("did_not_play"))
            reason = pr.get("reason")

            conn.execute(
                """
                INSERT INTO player_games (game_id, player_id, game_date, season, player_name,
                    team_id, opponent_id, home_away, minutes, fga, fgm, fg3a, fg3m, fta, ftm,
                    points, oreb, dreb, reb, ast, stl, blk, tov, pf, plus_minus, started, dnp_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(game_id, player_id) DO UPDATE SET
                    game_date = excluded.game_date, season = excluded.season,
                    player_name = excluded.player_name, team_id = excluded.team_id,
                    opponent_id = excluded.opponent_id, home_away = excluded.home_away,
                    minutes = excluded.minutes, fga = excluded.fga, fgm = excluded.fgm,
                    fg3a = excluded.fg3a, fg3m = excluded.fg3m, fta = excluded.fta, ftm = excluded.ftm,
                    points = excluded.points, oreb = excluded.oreb, dreb = excluded.dreb,
                    reb = excluded.reb, ast = excluded.ast, stl = excluded.stl, blk = excluded.blk,
                    tov = excluded.tov, pf = excluded.pf, plus_minus = excluded.plus_minus,
                    started = excluded.started, dnp_reason = excluded.dnp_reason
                """,
                (
                    game_id, pr["athlete_id"], str(pr["game_date"]), season, pr.get("athlete_display_name"),
                    pr.get("team_id"), pr.get("opponent_team_id"), pr.get("home_away"),
                    pr.get("minutes"), pr.get("field_goals_attempted"), pr.get("field_goals_made"),
                    pr.get("three_point_field_goals_attempted"), pr.get("three_point_field_goals_made"),
                    pr.get("free_throws_attempted"), pr.get("free_throws_made"), pr.get("points"),
                    pr.get("offensive_rebounds"), pr.get("defensive_rebounds"), pr.get("rebounds"),
                    pr.get("assists"), pr.get("steals"), pr.get("blocks"), pr.get("turnovers"),
                    pr.get("fouls"), plus_minus, int(bool(pr.get("starter"))), reason if did_not_play else None,
                ),
            )

            status = classify_status(did_not_play, reason)
            minutes_played = 0.0 if did_not_play else (pr.get("minutes") or 0.0)
            conn.execute(
                """
                INSERT INTO availability (game_id, player_id, team_id, status, minutes_played)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(game_id, player_id) DO UPDATE SET
                    team_id = excluded.team_id, status = excluded.status,
                    minutes_played = excluded.minutes_played
                """,
                (game_id, pr["athlete_id"], pr.get("team_id"), status, minutes_played),
            )

    return {"games": len(completed), "player_games": sum(len(player_box_by_game.get(r["id"], [])) for r in completed)}


def run_update() -> None:
    config = load_config()
    current_season = config["season"]
    stats_cfg = config["stats"]
    history_start = stats_cfg["history_start_season"]
    coef = stats_cfg["possession_fta_coefficient"]

    conn = get_connection()

    games_before = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    player_games_before = conn.execute("SELECT COUNT(*) FROM player_games").fetchone()[0]

    backfilled = _backfilled_seasons(conn)
    all_seasons = list(range(history_start, current_season + 1))
    seasons_to_fetch = [s for s in all_seasons if s == current_season or s not in backfilled]
    skipped = [s for s in all_seasons if s not in seasons_to_fetch]

    if skipped:
        log.info(
            "skipping %d already-backfilled season(s): %s",
            len(skipped), ", ".join(str(s) for s in skipped),
        )

    newly_backfilled = set()
    for season in seasons_to_fetch:
        log.info("fetching season %d...", season)
        _ingest_season(conn, season, coef)
        conn.commit()
        if season < current_season:
            newly_backfilled.add(season)

    if newly_backfilled:
        _mark_backfilled(conn, newly_backfilled)
        conn.commit()

    games_after = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    player_games_after = conn.execute("SELECT COUNT(*) FROM player_games").fetchone()[0]
    new_games = games_after - games_before
    new_player_games = player_games_after - player_games_before

    if new_games == 0:
        log.info("0 new games")
    else:
        log.info("%d new games, %d new player-games", new_games, new_player_games)

    last_game_date = conn.execute("SELECT MAX(game_date) FROM games").fetchone()[0]
    if last_game_date:
        _set_meta(conn, "last_ingested_game_date", last_game_date)
        conn.commit()

    _print_summary(conn, stats_cfg)
    _run_validations(conn, stats_cfg)

    conn.close()


def _print_summary(conn: sqlite3.Connection, stats_cfg: dict) -> None:
    seasons = [r[0] for r in conn.execute("SELECT DISTINCT season FROM games ORDER BY season")]
    n_games = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    n_player_games = conn.execute("SELECT COUNT(*) FROM player_games").fetchone()[0]
    n_players = conn.execute("SELECT COUNT(*) FROM players").fetchone()[0]
    n_teams = conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
    date_range = conn.execute("SELECT MIN(game_date), MAX(game_date) FROM games").fetchone()
    status_counts = dict(
        conn.execute("SELECT status, COUNT(*) FROM availability GROUP BY status").fetchall()
    )

    log.info("")
    log.info("=== Stats ingestion summary ===")
    log.info("seasons: %s", ", ".join(str(s) for s in seasons) if seasons else "(none)")
    log.info("games: %d", n_games)
    log.info("player-games: %d", n_player_games)
    log.info("players: %d, teams: %d", n_players, n_teams)
    log.info("date range: %s to %s", date_range[0], date_range[1])
    log.info("availability by status:")
    for status in ("played", "dnp_coach", "dnp_injury", "dnp_rest", "inactive", "not_on_roster"):
        log.info("  %-14s %d", status, status_counts.get(status, 0))
    if status_counts.get("not_on_roster", 0) == 0:
        log.info(
            "  (not_on_roster is always 0 in phase 1 -- distinguishing it from a normal "
            "DNP needs point-in-time roster/transaction data this phase doesn't build; see DECISIONS.md)"
        )


def _run_validations(conn: sqlite3.Connection, stats_cfg: dict) -> None:
    log.info("")
    log.info("=== Validation ===")
    _check_games_per_team(conn, stats_cfg["expected_games_per_team"])
    _check_team_minutes(conn, stats_cfg["team_minutes_tolerance"])
    _check_points_reconcile(conn)
    _check_rebounds_reconcile(conn)
    _check_no_duplicate_player_games(conn)
    _check_game_dates_in_season(conn)
    _check_player_fk(conn)
    _check_games_missing_player_data(conn)


def _check_games_missing_player_data(conn: sqlite3.Connection) -> None:
    """Not one of the spec's listed checks, but the same "never silently drop
    a row" standing rule applies to a completed game with no box score at all,
    not just a malformed one -- worth surfacing rather than letting it hide
    inside an otherwise-passing row count."""
    rows = conn.execute(
        """
        SELECT g.game_id, g.season, g.game_date FROM games g
        LEFT JOIN player_games pg ON pg.game_id = g.game_id
        WHERE pg.game_id IS NULL
        ORDER BY g.season, g.game_date
        """
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    if not rows:
        log.info("[PASS] every completed game (%d) has at least one player_games row", total)
        return
    by_season = Counter(season for _, season, _ in rows)
    log.info(
        "[INFO] %d of %d completed games have zero player_games rows -- box score "
        "not published by the source, not a parsing failure (by season: %s):",
        len(rows), total,
        ", ".join(f"{s}={n}" for s, n in sorted(by_season.items())),
    )
    for gid, season, game_date in rows[:20]:
        log.info("  game_id=%s season=%s game_date=%s", gid, season, game_date)


def _check_games_per_team(conn: sqlite3.Connection, expected: int) -> None:
    """Checks the *published schedule* (played + upcoming), not just games
    completed so far -- mid-season, completed-only counts would always show
    a deficit and the check would carry no signal."""
    current_season = conn.execute("SELECT MAX(season) FROM scheduled_games").fetchone()[0]
    rows = conn.execute(
        """
        SELECT t.display_name, COUNT(*)
        FROM scheduled_games sg JOIN teams t ON t.team_id = sg.team_id
        WHERE sg.season = ?
        GROUP BY t.display_name
        ORDER BY t.display_name
        """,
        (current_season,),
    ).fetchall()
    mismatches = [(name, n) for name, n in rows if n != expected]
    if not mismatches:
        log.info(
            "[PASS] scheduled games per team == %d for every team, season %s",
            expected, current_season,
        )
    else:
        log.info(
            "[INFO] scheduled games per team != %d for %d of %d team(s), season %s "
            "(real schedule deviations, e.g. Commissioner's Cup final -- not necessarily a bug):",
            expected, len(mismatches), len(rows), current_season,
        )
        for name, n in mismatches:
            log.info("  %-28s %d (expected %d, diff %+d)", name, n, expected, n - expected)


def _check_team_minutes(conn: sqlite3.Connection, tolerance: float) -> None:
    rows = conn.execute(
        """
        SELECT pg.game_id, pg.team_id, g.overtime_periods, SUM(COALESCE(pg.minutes, 0))
        FROM player_games pg JOIN games g ON g.game_id = pg.game_id
        GROUP BY pg.game_id, pg.team_id
        """
    ).fetchall()
    failures = []
    for game_id, team_id, ot, total_minutes in rows:
        expected = 200 + 25 * ot
        diff = total_minutes - expected
        if abs(diff) > tolerance:
            failures.append((game_id, team_id, total_minutes, expected, diff))
    if not failures:
        log.info(
            "[PASS] team minutes per game within +/-%g of 200 (+25/OT) for all %d team-games",
            tolerance, len(rows),
        )
    else:
        log.info(
            "[FAIL] %d team-game(s) outside the minutes tolerance "
            "(overwhelmingly 2002-2008 -- see DECISIONS.md; showing first 20):",
            len(failures),
        )
        for game_id, team_id, total_minutes, expected, diff in failures[:20]:
            log.info(
                "  game_id=%s team_id=%s minutes=%s expected=%s diff=%+.1f",
                game_id, team_id, total_minutes, expected, diff,
            )


def _check_points_reconcile(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        """
        SELECT game_id, player_id, fgm, fg3m, ftm, points FROM player_games
        WHERE points IS NOT NULL AND fgm IS NOT NULL AND fg3m IS NOT NULL AND ftm IS NOT NULL
        """
    ).fetchall()
    failures = [
        (gid, pid, fgm, fg3m, ftm, points)
        for gid, pid, fgm, fg3m, ftm, points in rows
        if 2 * (fgm - fg3m) + 3 * fg3m + ftm != points
    ]
    if not failures:
        log.info("[PASS] points reconcile (2*(FGM-FG3M)+3*FG3M+FTM == PTS) for all %d rows", len(rows))
    else:
        log.info("[FAIL] %d row(s) where points don't reconcile:", len(failures))
        for gid, pid, fgm, fg3m, ftm, points in failures[:20]:
            log.info(
                "  game_id=%s player_id=%s fgm=%s fg3m=%s ftm=%s points=%s (computed=%s)",
                gid, pid, fgm, fg3m, ftm, points, 2 * (fgm - fg3m) + 3 * fg3m + ftm,
            )


def _check_rebounds_reconcile(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT game_id, player_id, oreb, dreb, reb FROM player_games "
        "WHERE oreb IS NOT NULL AND dreb IS NOT NULL AND reb IS NOT NULL"
    ).fetchall()
    failures = [(gid, pid, o, d, r) for gid, pid, o, d, r in rows if o + d != r]
    if not failures:
        log.info("[PASS] REB == OREB+DREB for all %d rows", len(rows))
    else:
        log.info("[FAIL] %d row(s) where rebounds don't reconcile:", len(failures))
        for gid, pid, o, d, r in failures[:20]:
            log.info("  game_id=%s player_id=%s oreb=%s dreb=%s reb=%s", gid, pid, o, d, r)


def _check_no_duplicate_player_games(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT game_id, player_id, COUNT(*) FROM player_games GROUP BY game_id, player_id HAVING COUNT(*) > 1"
    ).fetchall()
    if not rows:
        log.info("[PASS] no player appears twice in the same game")
    else:
        log.info("[FAIL] %d player(s) appearing more than once in a game:", len(rows))
        for gid, pid, n in rows[:20]:
            log.info("  game_id=%s player_id=%s count=%s", gid, pid, n)


def _check_game_dates_in_season(conn: sqlite3.Connection) -> None:
    # WNBA seasons run roughly May-October; anything outside a generous
    # April-November window for its labeled season is worth a look.
    rows = conn.execute("SELECT game_id, season, game_date FROM games").fetchall()
    failures = []
    for gid, season, game_date in rows:
        month = int(str(game_date)[5:7])
        year = int(str(game_date)[0:4])
        if year != season or month < 4 or month > 11:
            failures.append((gid, season, game_date))
    if not failures:
        log.info("[PASS] no game date outside its season window, for all %d games", len(rows))
    else:
        log.info("[FAIL] %d game(s) with a date outside the expected season window:", len(failures))
        for gid, season, game_date in failures[:20]:
            log.info("  game_id=%s season=%s game_date=%s", gid, season, game_date)


def _check_player_fk(conn: sqlite3.Connection) -> None:
    rows = conn.execute(
        "SELECT DISTINCT pg.player_id FROM player_games pg "
        "LEFT JOIN players p ON p.player_id = pg.player_id WHERE p.player_id IS NULL"
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM player_games").fetchone()[0]
    if not rows:
        log.info("[PASS] every player_id in player_games (%d rows) exists in players", total)
    else:
        log.info("[FAIL] %d player_id(s) in player_games missing from players:", len(rows))
        for (pid,) in rows[:20]:
            log.info("  player_id=%s", pid)
