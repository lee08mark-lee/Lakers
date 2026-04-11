"""
nba_schedule.py

Fetches the NBA schedule and filters for Lakers (LAL) games.
Converts game times to America/Phoenix (no DST — always UTC-7).

Primary source: nba_api ScheduleLeagueV2 endpoint
Fallback: Direct CDN fetch
"""

import datetime
import time
import requests
import pytz

from cache import ttl_cache, invalidate_all  # noqa: F401 (re-export invalidate_all)

LAKERS_ABBREV = "LAL"
PHOENIX_TZ = pytz.timezone("America/Phoenix")
EASTERN_TZ = pytz.timezone("America/New_York")

# Fallback CDN URL (nba_api wraps the stats.nba.com version of this)
SCHEDULE_CDN_URL = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2.json"

CDN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.nba.com/",
    "Accept": "application/json",
}


def _fetch_schedule_nba_api() -> list[dict]:
    """Fetch schedule via nba_api (handles NBA headers automatically)."""
    from nba_api.stats.endpoints import ScheduleLeagueV2  # type: ignore
    endpoint = ScheduleLeagueV2(league_id="00")
    data = endpoint.get_dict()
    # The response structure wraps in resultSets or leagueSchedule depending on version
    # Try the direct dict path first
    league_schedule = data.get("leagueSchedule", {})
    if league_schedule:
        return _extract_game_dates(league_schedule)
    # Fallback: the nba_api may return a different structure
    raise ValueError("Unexpected nba_api response structure")


def _fetch_schedule_cdn() -> list[dict]:
    """Fetch schedule directly from NBA CDN (fallback)."""
    resp = requests.get(SCHEDULE_CDN_URL, headers=CDN_HEADERS, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    league_schedule = data.get("leagueSchedule", {})
    if not league_schedule:
        raise ValueError("Unexpected CDN response structure")
    return _extract_game_dates(league_schedule)


def _extract_game_dates(league_schedule: dict) -> list[dict]:
    """Extract raw game list from leagueSchedule structure."""
    game_dates = league_schedule.get("gameDates", [])
    games: list[dict] = []
    for date_entry in game_dates:
        for game in date_entry.get("games", []):
            games.append(game)
    return games


def _parse_game(game: dict) -> dict | None:
    """
    Parse a single NBA API game dict into our internal format.
    Returns None if the game is not a Lakers game.
    """
    home = game.get("homeTeam", {})
    away = game.get("awayTeam", {})

    home_abbrev = home.get("teamAbbreviation", "")
    away_abbrev = away.get("teamAbbreviation", "")

    if home_abbrev != LAKERS_ABBREV and away_abbrev != LAKERS_ABBREV:
        return None

    is_home = home_abbrev == LAKERS_ABBREV
    opponent_team = away if is_home else home
    opponent_name = f"{opponent_team.get('teamCity', '')} {opponent_team.get('teamName', '')}".strip()
    opponent_abbrev = opponent_team.get("teamAbbreviation", "")

    # Parse date/time — API provides Eastern time
    # gameDateTimeEst is the most reliable field when present
    game_datetime_est: datetime.datetime | None = None

    date_str = game.get("gameDateEst", "")       # e.g. "2025-10-22T00:00:00Z"
    time_str = game.get("gameTimeEst", "")        # e.g. "7:30 pm ET" or "19:30:00"
    game_et_str = game.get("gameDateTimeEst", "") # e.g. "2025-10-22T23:30:00Z"

    try:
        if game_et_str:
            # ISO format with Z suffix
            dt = datetime.datetime.fromisoformat(game_et_str.replace("Z", "+00:00"))
            game_datetime_est = dt.astimezone(EASTERN_TZ)
        elif date_str and time_str:
            # Parse date from ISO string, time from "7:30 pm ET" or "19:30:00"
            date_part = datetime.date.fromisoformat(date_str[:10])
            time_part = _parse_time_string(time_str)
            if time_part:
                naive = datetime.datetime.combine(date_part, time_part)
                game_datetime_est = EASTERN_TZ.localize(naive)
        elif date_str:
            date_part = datetime.date.fromisoformat(date_str[:10])
            game_datetime_est = EASTERN_TZ.localize(
                datetime.datetime.combine(date_part, datetime.time(0, 0))
            )
    except (ValueError, AttributeError):
        pass

    # Convert to Phoenix time
    if game_datetime_est:
        game_datetime_mt = game_datetime_est.astimezone(PHOENIX_TZ)
        date_display = game_datetime_mt.strftime("%a, %b %-d")
        time_display = game_datetime_mt.strftime("%-I:%M %p MT")
        sort_key = game_datetime_mt
    else:
        date_display = date_str[:10] if date_str else "TBD"
        time_display = "TBD"
        sort_key = datetime.datetime.min.replace(tzinfo=PHOENIX_TZ)

    # Broadcaster info
    broadcasters = game.get("broadcasters", {})
    national_broadcasters = broadcasters.get("nationalBroadcasters", [])
    home_tv_broadcasters = broadcasters.get("homeTvBroadcasters", [])
    away_tv_broadcasters = broadcasters.get("awayTvBroadcasters", [])

    # Game status
    game_status = game.get("gameStatus", 1)  # 1=scheduled, 2=live, 3=final
    game_status_text = game.get("gameStatusText", "").strip()

    return {
        "game_id": game.get("gameId", ""),
        "date_display": date_display,
        "time_display": time_display,
        "sort_key": sort_key,
        "opponent_name": opponent_name,
        "opponent_abbrev": opponent_abbrev,
        "is_home": is_home,
        "national_broadcasters": national_broadcasters,
        "home_tv_broadcasters": home_tv_broadcasters,
        "away_tv_broadcasters": away_tv_broadcasters,
        "game_status": game_status,
        "game_status_text": game_status_text,
        "arena_name": game.get("arenaName", ""),
        "arena_city": game.get("arenaCity", ""),
        "arena_state": game.get("arenaState", ""),
    }


def _parse_time_string(time_str: str) -> datetime.time | None:
    """Parse various time string formats from the NBA API."""
    import re
    time_str = time_str.strip()
    # "7:30 pm ET" or "7:30 PM ET"
    m = re.match(r"(\d{1,2}):(\d{2})\s*(am|pm)", time_str, re.IGNORECASE)
    if m:
        h, minute, meridiem = int(m.group(1)), int(m.group(2)), m.group(3).lower()
        if meridiem == "pm" and h != 12:
            h += 12
        elif meridiem == "am" and h == 12:
            h = 0
        return datetime.time(h, minute)
    # "19:30:00"
    m2 = re.match(r"(\d{2}):(\d{2})(?::\d{2})?", time_str)
    if m2:
        return datetime.time(int(m2.group(1)), int(m2.group(2)))
    return None


@ttl_cache(seconds=3600)
def get_lakers_games() -> tuple[list[dict], str]:
    """
    Fetch and return upcoming Lakers games with broadcast info.
    Returns (games_list, source_label).
    The list is sorted by game time and filtered to today and future.
    """
    raw_games: list[dict] = []
    source_label = "nba_api"

    try:
        raw_games = _fetch_schedule_nba_api()
    except Exception:
        try:
            raw_games = _fetch_schedule_cdn()
            source_label = "NBA CDN"
        except Exception as e:
            raise RuntimeError(
                f"Failed to fetch NBA schedule from all sources: {e}"
            ) from e

    # Filter for Lakers games and parse
    now_mt = datetime.datetime.now(PHOENIX_TZ)
    # Include games from today onward (don't filter out today's earlier games)
    today_mt = now_mt.replace(hour=0, minute=0, second=0, microsecond=0)

    parsed: list[dict] = []
    for game in raw_games:
        result = _parse_game(game)
        if result is None:
            continue
        # Include games from today onward, plus any already in-progress/final today
        if result["sort_key"] >= today_mt or result["game_status"] in (2, 3):
            if result["sort_key"] >= today_mt:
                parsed.append(result)

    parsed.sort(key=lambda g: g["sort_key"])
    return parsed, source_label
