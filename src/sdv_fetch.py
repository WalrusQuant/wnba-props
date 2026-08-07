"""Fetches WNBA box score / schedule data from sportsdataverse-data.

sportsdataverse-data (https://github.com/sportsdataverse/sportsdataverse-data)
publishes season-level parquet snapshots of ESPN's WNBA box scores and
schedules as GitHub release assets, refreshed on a regular cadence. This
project's sandboxed network policy allows GitHub release-asset downloads but
blocks direct calls to stats.wnba.com and ESPN's API, so this is the
practical way to reach sportsdataverse's data — the source the project guide
ranks first — without depending on the full `sportsdataverse` package, which
pulls in a much heavier dependency tree (xgboost, scikit-learn, pillow, ...)
than a handful of parquet downloads needs. See DECISIONS.md.
"""

import io
import json
import urllib.error
import urllib.request
from pathlib import Path

import pyarrow.parquet as pq

RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "stats"

_RELEASE_TAGS = {
    "schedule": "espn_wnba_schedules",
    "player_box": "espn_wnba_player_boxscores",
    "team_box": "espn_wnba_team_boxscores",
}
_FILE_PREFIXES = {
    "schedule": "wnba_schedule",
    "player_box": "player_box",
    "team_box": "team_box",
}

_BASE = "https://github.com/sportsdataverse/sportsdataverse-data/releases/download"


def _asset_url(dataset: str, season: int) -> str:
    tag = _RELEASE_TAGS[dataset]
    prefix = _FILE_PREFIXES[dataset]
    return f"{_BASE}/{tag}/{prefix}_{season}.parquet"


def fetch_season(dataset: str, season: int) -> list[dict] | None:
    """Download one season's parquet release asset, save it as raw JSON, and
    return the parsed rows. Returns None if the season has no published asset
    (some seasons have no team_box, and no data before 2002 exists at all)."""
    url = _asset_url(dataset, season)
    req = urllib.request.Request(url, headers={"User-Agent": "wnba-props/0.1 (+data ingestion)"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw_bytes = resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise

    table = pq.read_table(io.BytesIO(raw_bytes))
    rows = table.to_pylist()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    raw_path = RAW_DIR / f"{dataset}_{season}.json"
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(rows, f, default=str)

    return rows
