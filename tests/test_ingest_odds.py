"""Tests the odds-snapshot parser against a synthetic fixture shaped like a
real The Odds API event-odds response. Network access to the-odds-api.com is
blocked from this sandbox and no ODDS_API_KEY is configured yet, so this is
the only way to verify the parser without a real capture -- the fixture
below is not real market data and nothing here touches data/raw/ or
data/wnba.db.
"""

from src.ingest_odds import _parse_event_odds

SAMPLE_EVENT_ODDS = {
    "id": "e912304e5091d3c56ff6a1f2c3d4b5a6",
    "sport_key": "basketball_wnba",
    "commence_time": "2026-08-07T23:00:00Z",
    "home_team": "New York Liberty",
    "away_team": "Las Vegas Aces",
    "bookmakers": [
        {
            "key": "draftkings",
            "title": "DraftKings",
            "last_update": "2026-08-07T20:00:00Z",
            "markets": [
                {
                    "key": "player_points",
                    "last_update": "2026-08-07T20:00:00Z",
                    "outcomes": [
                        {"name": "Over", "description": "A'ja Wilson", "price": -115, "point": 22.5},
                        {"name": "Under", "description": "A'ja Wilson", "price": -105, "point": 22.5},
                        {"name": "Over", "description": "Breanna Stewart", "price": -110, "point": 19.5},
                        {"name": "Under", "description": "Breanna Stewart", "price": -110, "point": 19.5},
                    ],
                },
                {
                    "key": "player_points_alternate",
                    "last_update": "2026-08-07T20:00:00Z",
                    "outcomes": [
                        {"name": "Over", "description": "A'ja Wilson", "price": -200, "point": 18.5},
                        {"name": "Under", "description": "A'ja Wilson", "price": 165, "point": 18.5},
                    ],
                },
            ],
        },
        {
            "key": "fanduel",
            "title": "FanDuel",
            "last_update": "2026-08-07T20:01:00Z",
            "markets": [
                {
                    "key": "player_rebounds",
                    "last_update": "2026-08-07T20:01:00Z",
                    "outcomes": [
                        {"name": "Over", "description": "A'ja Wilson", "price": -120, "point": 9.5},
                        {"name": "Under", "description": "A'ja Wilson", "price": 100, "point": 9.5},
                    ],
                },
                {
                    "key": "player_points",
                    "last_update": "2026-08-07T20:01:00Z",
                    "outcomes": [
                        {"name": "Over", "description": "A'ja Wilson", "price": -110, "point": 22.5},
                        {"name": "Under", "description": "A'ja Wilson", "price": -110, "point": 22.5},
                    ],
                },
            ],
        },
    ],
}

NO_PROPS_EVENT = {
    "id": "deadbeef00000000000000000000000",
    "commence_time": "2026-08-07T23:00:00Z",
    "home_team": "Chicago Sky",
    "away_team": "Atlanta Dream",
    "bookmakers": [],
}


def test_parses_over_under_pairs_into_one_row():
    rows = _parse_event_odds(SAMPLE_EVENT_ODDS, "2026-08-07T20-05-00Z", markets=["player_points"])
    # player_rebounds is configured off in this call and must be dropped even
    # though FanDuel posted it.
    assert all(r[6] != "player_rebounds" for r in rows)

    dk_main = [r for r in rows if r[5] == "draftkings" and r[6] == "player_points" and r[7] == "A'ja Wilson"]
    assert len(dk_main) == 1
    row = dk_main[0]
    (
        captured_at, game_id, commence_time, home_team, away_team,
        book, market, player, line, over_price, under_price, is_alternate,
    ) = row
    assert captured_at == "2026-08-07T20-05-00Z"
    assert game_id == SAMPLE_EVENT_ODDS["id"]
    assert player == "A'ja Wilson"
    assert line == 22.5
    assert over_price == -115
    assert under_price == -105
    assert is_alternate == 0


def test_alternate_market_flagged_and_kept_separate_from_main_line():
    rows = _parse_event_odds(SAMPLE_EVENT_ODDS, "2026-08-07T20-05-00Z", markets=["player_points"])
    wilson_rows = [r for r in rows if r[5] == "draftkings" and r[7] == "A'ja Wilson"]
    lines = {(r[8], r[11]) for r in wilson_rows}
    assert (22.5, 0) in lines
    assert (18.5, 1) in lines


def test_missing_market_at_a_book_does_not_crash_or_appear():
    # DraftKings never posted player_rebounds; only FanDuel did, and it's
    # excluded here since only player_points was requested.
    rows = _parse_event_odds(SAMPLE_EVENT_ODDS, "2026-08-07T20-05-00Z", markets=["player_points"])
    assert not any(r[6] == "player_rebounds" for r in rows)


def test_event_with_no_props_posted_yields_no_rows_not_an_error():
    rows = _parse_event_odds(NO_PROPS_EVENT, "2026-08-07T20-05-00Z", markets=["player_points"])
    assert rows == []


def test_multiple_books_for_same_player_market_all_kept():
    rows = _parse_event_odds(SAMPLE_EVENT_ODDS, "2026-08-07T20-05-00Z", markets=["player_points"])
    wilson_main_line_books = {r[5] for r in rows if r[7] == "A'ja Wilson" and r[8] == 22.5 and r[11] == 0}
    assert wilson_main_line_books == {"draftkings", "fanduel"}
