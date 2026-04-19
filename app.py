"""
app.py — Lakers Streaming Finder

Flask web app that shows upcoming Lakers games and tells you
where to watch them from Phoenix, AZ with NBA League Pass via Amazon Prime.
"""

import time
import datetime
import pytz

from flask import Flask, render_template, jsonify, redirect, url_for

import cache as cache_module
from nba_schedule import get_lakers_games
from broadcast_mapper import get_watch_info

app = Flask(__name__)

PHOENIX_TZ = pytz.timezone("America/Phoenix")


def _build_game_cards() -> tuple[list[dict], str, str]:
    """
    Fetch Lakers schedule and enrich each game with watch info.
    Returns (game_cards, source_label, fetched_at_str).
    """
    games, source_label = get_lakers_games()

    cards = []
    for game in games:
        watch = get_watch_info(
            national_broadcasters=game["national_broadcasters"],
            home_tv_broadcasters=game["home_tv_broadcasters"],
            away_tv_broadcasters=game["away_tv_broadcasters"],
        )

        # Build display strings for networks
        all_networks = watch.national_networks + watch.local_networks
        networks_display = ", ".join(all_networks) if all_networks else "TBD"

        cards.append({
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
            # Watch info
            "is_blacked_out": watch.is_blacked_out,
            "league_pass_available": watch.league_pass_available,
            "watch_on": [
                {
                    "service": opt.service,
                    "url": opt.url,
                    "note": opt.note,
                }
                for opt in watch.watch_on
            ],
            "networks_display": networks_display,
            "prime_video_national": watch.prime_video_national,
        })

    fetched_at = datetime.datetime.now(PHOENIX_TZ).strftime("%b %-d, %Y %-I:%M %p MT")
    return cards, source_label, fetched_at


@app.route("/")
def index():
    error = None
    cards = []
    source_label = ""
    fetched_at = ""

    try:
        cards, source_label, fetched_at = _build_game_cards()
    except RuntimeError as e:
        error = str(e)

    return render_template(
        "index.html",
        games=cards,
        error=error,
        source_label=source_label,
        fetched_at=fetched_at,
    )


@app.route("/api/games")
def api_games():
    try:
        cards, source_label, fetched_at = _build_game_cards()
        return jsonify({
            "ok": True,
            "source": source_label,
            "fetched_at": fetched_at,
            "count": len(cards),
            "games": cards,
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
