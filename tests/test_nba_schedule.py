"""Tests for nba_schedule.py parsing and filtering logic."""

import datetime
import pytz
import pytest

from nba_schedule import _parse_game, _parse_time_string, PHOENIX_TZ


def make_game(home_abbrev="LAL", away_abbrev="GSW", national=None, time_str=None):
    return {
        "gameId": "0022500099",
        "gameDateEst": "2025-12-25T00:00:00Z",
        "gameTimeEst": time_str or "7:30 pm ET",
        "gameDateTimeEst": "",
        "homeTeam": {
            "teamAbbreviation": home_abbrev,
            "teamCity": "Los Angeles" if home_abbrev == "LAL" else "Golden State",
            "teamName": "Lakers" if home_abbrev == "LAL" else "Warriors",
        },
        "awayTeam": {
            "teamAbbreviation": away_abbrev,
            "teamCity": "Golden State" if away_abbrev == "GSW" else "Los Angeles",
            "teamName": "Warriors" if away_abbrev == "GSW" else "Lakers",
        },
        "broadcasters": {
            "nationalBroadcasters": national or [],
            "homeTvBroadcasters": [],
            "awayTvBroadcasters": [],
        },
        "gameStatus": 1,
        "gameStatusText": "7:30 pm ET",
        "arenaName": "Crypto.com Arena",
        "arenaCity": "Los Angeles",
        "arenaState": "CA",
    }


# ── Game filtering ────────────────────────────────────────────────────────────

def test_lakers_home_game_is_parsed():
    result = _parse_game(make_game(home_abbrev="LAL", away_abbrev="GSW"))
    assert result is not None
    assert result["is_home"] is True
    assert "Golden State Warriors" in result["opponent_name"]


def test_lakers_away_game_is_parsed():
    result = _parse_game(make_game(home_abbrev="GSW", away_abbrev="LAL"))
    assert result is not None
    assert result["is_home"] is False
    assert "Golden State Warriors" in result["opponent_name"]


def test_non_lakers_game_returns_none():
    result = _parse_game(make_game(home_abbrev="BOS", away_abbrev="GSW"))
    assert result is None


# ── Time parsing ──────────────────────────────────────────────────────────────

def test_time_display_ends_with_mt():
    result = _parse_game(make_game(time_str="7:30 pm ET"))
    assert result is not None
    assert "MT" in result["time_display"]


def test_phoenix_timezone_no_dst():
    """Phoenix is always UTC-7, never UTC-6."""
    result = _parse_game(make_game(time_str="7:30 pm ET"))
    assert result is not None
    tz = result["time_display"]
    # 7:30 PM ET = 5:30 PM MT (UTC-7)
    assert "5:30" in tz


@pytest.mark.parametrize("time_str,expected_h,expected_m", [
    ("7:30 pm ET", 19, 30),
    ("12:00 pm ET", 12, 0),
    ("12:00 am ET", 0, 0),
    ("10:00 am ET", 10, 0),
])
def test_parse_time_string_variants(time_str, expected_h, expected_m):
    t = _parse_time_string(time_str)
    assert t is not None
    assert t.hour == expected_h
    assert t.minute == expected_m


def test_parse_time_string_24h_format():
    t = _parse_time_string("19:30:00")
    assert t is not None
    assert t.hour == 19
    assert t.minute == 30


def test_parse_time_string_invalid_returns_none():
    assert _parse_time_string("TBD") is None
    assert _parse_time_string("") is None


# ── Broadcaster passthrough ───────────────────────────────────────────────────

def test_national_broadcasters_passed_through():
    national = [{"broadcasterDisplay": "ESPN", "broadcasterAbbreviation": "ESPN"}]
    result = _parse_game(make_game(national=national))
    assert result is not None
    assert result["national_broadcasters"] == national


def test_empty_national_broadcasters_when_local_only():
    result = _parse_game(make_game(national=[]))
    assert result is not None
    assert result["national_broadcasters"] == []


# ── Game ID passthrough ───────────────────────────────────────────────────────

def test_game_id_is_preserved():
    result = _parse_game(make_game())
    assert result is not None
    assert result["game_id"] == "0022500099"
