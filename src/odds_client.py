"""Thin client for The Odds API (the-odds-api.com, with hyphens -- the
unhyphenated theoddsapi.com is an unaffiliated impersonator).

WNBA player props live on the per-event odds endpoint: list events for the
sport, then fetch odds one event at a time. The API key travels as a query
parameter, so every function here is careful to never let it reach a log
line or a saved file -- only the response body gets written to disk.
"""

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

BASE_URL = "https://api.the-odds-api.com/v4"
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw" / "odds"


class OddsApiError(Exception):
    """Raised for HTTP/response errors from The Odds API. Never includes the API key."""


@dataclass
class Quota:
    remaining: int | None
    used: int | None
    last_cost: int | None


def _get(path: str, api_key: str, params: dict) -> tuple[dict | list, Quota]:
    query = dict(params)
    query["apiKey"] = api_key
    url = f"{BASE_URL}{path}?{urllib.parse.urlencode(query)}"
    req = urllib.request.Request(url, headers={"User-Agent": "wnba-props/0.1 (+odds ingestion)"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            headers = resp.headers
    except urllib.error.HTTPError as e:
        # e.read() / str(e) never include the request URL, so this is safe to log.
        raise OddsApiError(f"HTTP {e.code} from {path}: {e.read().decode(errors='replace')[:500]}") from e
    except urllib.error.URLError as e:
        raise OddsApiError(f"network error calling {path}: {e.reason}") from e

    quota = Quota(
        remaining=_int_or_none(headers.get("x-requests-remaining")),
        used=_int_or_none(headers.get("x-requests-used")),
        last_cost=_int_or_none(headers.get("x-requests-last")),
    )
    try:
        data = json.loads(body)
    except json.JSONDecodeError as e:
        raise OddsApiError(f"malformed JSON from {path}: {e}") from e
    return data, quota


def _int_or_none(s: str | None) -> int | None:
    try:
        return int(s) if s is not None else None
    except ValueError:
        return None


def _save_raw(kind: str, payload) -> tuple[str, Path]:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    captured_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    path = RAW_DIR / f"{captured_at}__{kind}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, default=str)
    return captured_at, path


def fetch_events(api_key: str, sport_key: str) -> tuple[list[dict], Quota, str]:
    """Lists upcoming events for the sport. Saves the raw response first."""
    data, quota = _get(f"/sports/{sport_key}/events", api_key, {})
    captured_at, _ = _save_raw("events", data)
    if not isinstance(data, list):
        raise OddsApiError(f"expected a list of events, got {type(data).__name__}")
    return data, quota, captured_at


def fetch_event_odds(
    api_key: str, sport_key: str, event_id: str, markets: list[str], regions: list[str], price_format: str
) -> tuple[dict, Quota, str]:
    """Fetches player-prop odds for one event. Saves the raw response first."""
    odds_format = "american" if price_format == "american" else "decimal"
    data, quota = _get(
        f"/sports/{sport_key}/events/{event_id}/odds",
        api_key,
        {
            "regions": ",".join(regions),
            "markets": ",".join(markets),
            "oddsFormat": odds_format,
            "dateFormat": "iso",
        },
    )
    captured_at, _ = _save_raw(f"event_{event_id}", data)
    if not isinstance(data, dict):
        raise OddsApiError(f"expected an object for event {event_id}, got {type(data).__name__}")
    return data, quota, captured_at


def latest_raw_files() -> list[Path]:
    """The most recent capture run's raw files: every file sharing the newest
    timestamp prefix (an events file plus one event-odds file per game)."""
    if not RAW_DIR.exists():
        return []
    files = sorted(RAW_DIR.glob("*.json"))
    if not files:
        return []
    newest_prefix = files[-1].name.split("__")[0]
    return [f for f in files if f.name.startswith(newest_prefix)]
