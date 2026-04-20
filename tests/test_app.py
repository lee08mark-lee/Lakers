"""Integration tests for Flask routes in app.py."""

import json
import pytest
import cache as cache_module
import app as flask_app


MOCK_UPCOMING = [
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
        "lakers_score": None,
        "opponent_score": None,
        "lakers_won": None,
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
        "lakers_score": None,
        "opponent_score": None,
        "lakers_won": None,
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
        "lakers_score": None,
        "opponent_score": None,
        "lakers_won": None,
    },
]

MOCK_LAST_GAME = {
    "game_id": "0022400999",
    "date_display": "Tue, Apr 15",
    "time_display": "7:00 PM MT",
    "sort_key": None,
    "opponent_name": "Denver Nuggets",
    "opponent_abbrev": "DEN",
    "is_home": True,
    "national_broadcasters": [],
    "home_tv_broadcasters": [],
    "away_tv_broadcasters": [],
    "game_status": 3,
    "game_status_text": "Final",
    "arena_name": "Crypto.com Arena",
    "arena_city": "Los Angeles",
    "arena_state": "CA",
    "lakers_score": 118,
    "opponent_score": 112,
    "lakers_won": True,
}


@pytest.fixture(autouse=True)
def mock_schedule(monkeypatch):
    cache_module.invalidate_all()
    monkeypatch.setattr(flask_app, "get_lakers_games", lambda: (MOCK_UPCOMING, "mock"))
    monkeypatch.setattr(flask_app, "get_last_lakers_game", lambda: (MOCK_LAST_GAME, "mock"))


@pytest.fixture()
def client():
    flask_app.app.config["TESTING"] = True
    with flask_app.app.test_client() as c:
        yield c


# ── / (HTML) ──────────────────────────────────────────────────────────────────

def test_index_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_index_shows_lakers_logo(client):
    body = client.get("/").data.decode()
    assert "1610612747" in body  # Lakers team ID in logo URL


def test_index_shows_last_game_score(client):
    body = client.get("/").data.decode()
    assert "118" in body
    assert "112" in body
    assert "DEN" in body


def test_index_shows_last_game_result(client):
    body = client.get("/").data.decode()
    assert "FINAL" in body or "final" in body.lower()


def test_index_shows_next_game_opponent(client):
    body = client.get("/").data.decode()
    assert "Golden State Warriors" in body


def test_index_shows_next_game_datetime(client):
    body = client.get("/").data.decode()
    assert "Apr 17" in body
    assert "MT" in body


def test_index_shows_where_to_watch(client):
    body = client.get("/").data.decode()
    assert "WHERE TO WATCH" in body or "where to watch" in body.lower()


def test_index_shows_blacked_out_for_espn_next_game(client):
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
    assert client.get("/api/games").status_code == 200


def test_api_games_ok(client):
    data = json.loads(client.get("/api/games").data)
    assert data["ok"] is True
    assert data["count"] == 3


def test_api_includes_next_game(client):
    data = json.loads(client.get("/api/games").data)
    assert data["next_game"] is not None
    assert data["next_game"]["game_id"] == "0022500001"


def test_api_includes_last_game(client):
    data = json.loads(client.get("/api/games").data)
    lg = data["last_game"]
    assert lg is not None
    assert lg["lakers_score"] == 118
    assert lg["opponent_score"] == 112
    assert lg["lakers_won"] is True


def test_api_espn_game_is_blacked_out(client):
    games = json.loads(client.get("/api/games").data)["games"]
    espn_game = next(g for g in games if g["game_id"] == "0022500001")
    assert espn_game["is_blacked_out"] is True
    assert espn_game["league_pass_available"] is False


def test_api_local_game_has_league_pass(client):
    games = json.loads(client.get("/api/games").data)["games"]
    local_game = next(g for g in games if g["game_id"] == "0022500002")
    assert local_game["league_pass_available"] is True


def test_api_prime_game_flagged(client):
    games = json.loads(client.get("/api/games").data)["games"]
    prime_game = next(g for g in games if g["game_id"] == "0022500003")
    assert prime_game["prime_video_national"] is True


def test_api_games_all_have_watch_on(client):
    games = json.loads(client.get("/api/games").data)["games"]
    for game in games:
        assert len(game["watch_on"]) >= 1


# ── /refresh ──────────────────────────────────────────────────────────────────

def test_refresh_redirects(client):
    resp = client.get("/refresh")
    assert resp.status_code in (301, 302)
