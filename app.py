"""
app.py — Lakers Streaming Finder

Flask web app that shows upcoming Lakers games and tells you
where to watch them from Phoenix, AZ with NBA League Pass via Amazon Prime.
"""

import datetime
import pytz

from flask import Flask, render_template, jsonify, redirect, url_for

import cache as cache_module
from nba_schedule import get_lakers_games, get_last_lakers_game
from broadcast_mapper import get_watch_info

app = Flask(__name__)

PHOENIX_TZ = pytz.timezone("America/Phoenix")

# NBA CDN team logo (Lakers team ID: 1610612747)
LAKERS_LOGO_URL = "https://cdn.nba.com/logos/nba/1610612747/global/L/logo.svg"


def _enrich_game(game: dict) -> dict:
    """Add watch info and display fields to a parsed game dict."""
    watch = get_watch_info(
        national_broadcasters=game["national_broadcasters"],
        home_tv_broadcasters=game["home_tv_broadcasters"],
        away_tv_broadcasters=game["away_tv_broadcasters"],
    )
    all_networks = watch.national_networks + watch.local_networks
    return {
        "game_id": game["game_id"],
        "date_display": game["date_display"],
        "time_display": game["time_display"],
        "opponent_name": game["opponent_name"],
        "opponent_abbrev": game["opponent_abbrev"],
        "is_home": game["is_home"],
        "matchup": (
            f"Lakers vs {game['opponent_name']}"
            if game["is_home"]
            else f"Lakers @ {game['opponent_name']}"
        ),
        "game_status": game["game_status"],
        "game_status_text": game["game_status_text"],
        "arena_name": game["arena_name"],
        "arena_city": game["arena_city"],
        "arena_state": game["arena_state"],
        # Score fields
        "lakers_score": game["lakers_score"],
        "opponent_score": game["opponent_score"],
        "lakers_won": game["lakers_won"],
        # Watch info
        "is_blacked_out": watch.is_blacked_out,
        "league_pass_available": watch.league_pass_available,
        "watch_on": [
            {"service": opt.service, "url": opt.url, "note": opt.note}
            for opt in watch.watch_on
        ],
        "networks_display": ", ".join(all_networks) if all_networks else "TBD",
        "prime_video_national": watch.prime_video_national,
    }


def _build_page_data() -> dict:
    """Build all data needed for the index page."""
    upcoming_games, source_label = get_lakers_games()
    last_game_raw, _ = get_last_lakers_game()

    cards = [_enrich_game(g) for g in upcoming_games]
    next_game = cards[0] if cards else None
    last_game = _enrich_game(last_game_raw) if last_game_raw else None
    fetched_at = datetime.datetime.now(PHOENIX_TZ).strftime("%b %-d, %Y %-I:%M %p MT")

    return {
        "games": cards,
        "next_game": next_game,
        "last_game": last_game,
        "source_label": source_label,
        "fetched_at": fetched_at,
        "lakers_logo_url": LAKERS_LOGO_URL,
    }


@app.route("/")
def index():
    error = None
    data: dict = {
        "games": [],
        "next_game": None,
        "last_game": None,
        "source_label": "",
        "fetched_at": "",
        "lakers_logo_url": LAKERS_LOGO_URL,
    }
    try:
        data = _build_page_data()
    except RuntimeError as e:
        error = str(e)

    return render_template("index.html", error=error, **data)


@app.route("/api/games")
def api_games():
    try:
        data = _build_page_data()
        return jsonify({
            "ok": True,
            "source": data["source_label"],
            "fetched_at": data["fetched_at"],
            "count": len(data["games"]),
            "next_game": data["next_game"],
            "last_game": data["last_game"],
            "games": data["games"],
        })
    except RuntimeError as e:
        return jsonify({"ok": False, "error": str(e)}), 503


@app.route("/refresh")
def refresh():
    cache_module.invalidate_all()
    return redirect(url_for("index"))


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8000))
    app.run(debug=True, host="0.0.0.0", port=port)
