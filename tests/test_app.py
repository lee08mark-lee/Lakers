"""Integration tests for Flask routes in app.py."""

import json
import pytest
import cache as cache_module
import app as flask_app


MOCK_GAMES = [
    {
        "game_id": "0022500001",
        "date_display": "Thu, Apr 17",
        "time_display": "7:30 PM MT",
        "sort_key": None,
        "opponent_name": "Golden State Warriors",
        "opponent_abbrev": "GSW",
        "is_home": True,
        "national_broadcasters": [
            {"broadcasterDisplay": "ESPN", "broadcasterAbbreviation": "ESPN"}
        ],
        "home_tv_broadcasters": [
            {"broadcasterDisplay": "Spectrum SportsNet", "broadcasterAbbreviation": "SPSN"}
        ],
        "away_tv_broadcasters": [],
        "game_status": 1,
        "game_status_text": "7:30 pm ET",
        "arena_name": "Crypto.com Arena",
        "arena_city": "Los Angeles",
        "arena_state": "CA",
    },
    {
        "game_id": "0022500002",
        "date_display": "Sat, Apr 19",
        "time_display": "5:00 PM MT",
        "sort_key": None,
        "opponent_name": "Memphis Grizzlies",
        "opponent_abbrev": "MEM",
        "is_home": False,
        "national_broadcasters": [],
        "home_tv_broadcasters": [
            {"broadcasterDisplay": "Bally Sports Southeast", "broadcasterAbbreviation": "BSSE"}
        ],
        "away_tv_broadcasters": [],
        "game_status": 1,
        "game_status_text": "7:00 pm ET",
        "arena_name": "FedExForum",
        "arena_city": "Memphis",
        "arena_state": "TN",
    },
    {
        "game_id": "0022500003",
        "date_display": "Thu, Apr 24",
        "time_display": "6:00 PM MT",
        "sort_key": None,
        "opponent_name": "Phoenix Suns",
        "opponent_abbrev": "PHX",
        "is_home": False,
        "national_broadcasters": [
            {"broadcasterDisplay": "Prime Video", "broadcasterAbbreviation": "PRIME"}
        ],
        "home_tv_broadcasters": [],
        "away_tv_broadcasters": [],
        "game_status": 1,
        "game_status_text": "9:00 pm ET",
        "arena_name": "Footprint Center",
        "arena_city": "Phoenix",
        "arena_state": "AZ",
    },
]


@pytest.fixture(autouse=True)
def mock_schedule(monkeypatch):
    cache_module.invalidate_all()
    monkeypatch.setattr(flask_app, "get_lakers_games", lambda: (MOCK_GAMES, "mock"))


@pytest.fixture()
def client():
    flask_app.app.config["TESTING"] = True
    with flask_app.app.test_client() as c:
        yield c


# ── / (HTML) ──────────────────────────────────────────────────────────────────

def test_index_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_index_shows_all_opponents(client):
    body = client.get("/").data.decode()
    assert "Golden State Warriors" in body
    assert "Memphis Grizzlies" in body
    assert "Phoenix Suns" in body


def test_index_shows_blacked_out_for_espn_game(client):
    body = client.get("/").data.decode().lower()
    assert "blacked out" in body


def test_index_shows_league_pass_for_local_game(client):
    body = client.get("/").data.decode()
    assert "League Pass" in body


def test_index_shows_prime_video_for_amazon_game(client):
    body = client.get("/").data.decode()
    assert "Amazon Prime Video" in body


def test_index_shows_phoenix_timezone(client):
    body = client.get("/").data.decode()
    assert "MT" in body


# ── /api/games (JSON) ─────────────────────────────────────────────────────────

def test_api_games_returns_200(client):
    resp = client.get("/api/games")
    assert resp.status_code == 200


def test_api_games_returns_json(client):
    resp = client.get("/api/games")
    data = json.loads(resp.data)
    assert data["ok"] is True
    assert data["count"] == 3
    assert len(data["games"]) == 3


def test_api_espn_game_is_blacked_out(client):
    games = json.loads(client.get("/api/games").data)["games"]
    espn_game = next(g for g in games if g["game_id"] == "0022500001")
    assert espn_game["is_blacked_out"] is True
    assert espn_game["league_pass_available"] is False


def test_api_local_game_has_league_pass(client):
    games = json.loads(client.get("/api/games").data)["games"]
    local_game = next(g for g in games if g["game_id"] == "0022500002")
    assert local_game["league_pass_available"] is True
    assert local_game["is_blacked_out"] is False


def test_api_prime_game_flagged_correctly(client):
    games = json.loads(client.get("/api/games").data)["games"]
    prime_game = next(g for g in games if g["game_id"] == "0022500003")
    assert prime_game["is_blacked_out"] is True
    assert prime_game["prime_video_national"] is True


def test_api_games_includes_watch_on_services(client):
    games = json.loads(client.get("/api/games").data)["games"]
    for game in games:
        assert len(game["watch_on"]) >= 1
        for opt in game["watch_on"]:
            assert "service" in opt
            assert "url" in opt


# ── /refresh ──────────────────────────────────────────────────────────────────

def test_refresh_redirects(client):
    resp = client.get("/refresh")
    assert resp.status_code in (301, 302)
    assert "/" in resp.headers.get("Location", "")
