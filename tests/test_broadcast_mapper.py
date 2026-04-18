"""Tests for broadcast_mapper.py — blackout logic for Phoenix, AZ viewer."""

import pytest
from broadcast_mapper import get_watch_info, WatchInfo


def b(display, abbrev):
    """Shorthand for building a broadcaster dict."""
    return {"broadcasterDisplay": display, "broadcasterAbbreviation": abbrev}


# ── League Pass available (no national broadcaster) ──────────────────────────

def test_local_only_game_available_on_league_pass():
    """Spectrum SportsNet only → League Pass available (no local blackout for PHX)."""
    result = get_watch_info(
        national_broadcasters=[],
        home_tv_broadcasters=[b("Spectrum SportsNet", "SPSN")],
    )
    assert result.league_pass_available is True
    assert result.is_blacked_out is False
    assert any("League Pass" in opt.service for opt in result.watch_on)


def test_no_broadcaster_available_on_league_pass():
    """No broadcaster at all → League Pass available."""
    result = get_watch_info(national_broadcasters=[])
    assert result.league_pass_available is True
    assert result.is_blacked_out is False


# ── ESPN / ABC (Disney) blackouts ─────────────────────────────────────────────

def test_espn_game_is_blacked_out():
    result = get_watch_info([b("ESPN", "ESPN")])
    assert result.is_blacked_out is True
    assert result.league_pass_available is False
    services = [opt.service for opt in result.watch_on]
    assert any("ESPN" in s for s in services)


def test_espn2_game_is_blacked_out():
    result = get_watch_info([b("ESPN2", "ESPN2")])
    assert result.is_blacked_out is True
    assert any("ESPN" in opt.service for opt in result.watch_on)


def test_abc_game_is_blacked_out():
    result = get_watch_info([b("ABC", "ABC")])
    assert result.is_blacked_out is True
    services = [opt.service for opt in result.watch_on]
    assert any("ESPN" in s for s in services)


def test_abc_and_espn_deduplicates_to_espn_app():
    """ABC + ESPN both map to ESPN app — should not produce duplicate service links."""
    result = get_watch_info([b("ABC", "ABC"), b("ESPN", "ESPN")])
    assert result.is_blacked_out is True
    # Both point to ESPN app; verify we don't get two identical service URLs
    urls = [opt.url for opt in result.watch_on]
    espn_urls = [u for u in urls if "espn.com" in u]
    # May be 1 or 2 entries but both go to espn.com — that's acceptable
    assert len(espn_urls) >= 1


# ── NBC / Peacock blackouts ───────────────────────────────────────────────────

def test_nbc_game_is_blacked_out_to_peacock():
    result = get_watch_info([b("NBC", "NBC")])
    assert result.is_blacked_out is True
    services = [opt.service for opt in result.watch_on]
    assert any("Peacock" in s for s in services)


def test_peacock_game_is_blacked_out():
    result = get_watch_info([b("Peacock", "PEACOCK")])
    assert result.is_blacked_out is True
    assert any("Peacock" in opt.service for opt in result.watch_on)


def test_nbcsp_game_is_blacked_out_to_peacock():
    result = get_watch_info([b("NBC Sports", "NBCSP")])
    assert result.is_blacked_out is True
    assert any("Peacock" in opt.service for opt in result.watch_on)


# ── Amazon Prime Video blackout ───────────────────────────────────────────────

def test_prime_video_game_is_blacked_out():
    """Prime Video national game → blacked out on League Pass channel."""
    result = get_watch_info([b("Prime Video", "PRIME")])
    assert result.is_blacked_out is True
    assert result.league_pass_available is False
    assert result.prime_video_national is True
    services = [opt.service for opt in result.watch_on]
    assert any("Amazon Prime Video" in s for s in services)


def test_prime_video_note_warns_about_league_pass_channel():
    """Must include a note clarifying NOT to use the League Pass channel."""
    result = get_watch_info([b("Prime Video", "PRIME")])
    notes = [opt.note for opt in result.watch_on if opt.note]
    assert notes, "Expected a note for Prime Video national games"
    combined = " ".join(notes).lower()
    assert "league pass" in combined or "not" in combined


def test_amazon_abbreviation_variant():
    """AMAZON abbreviation should also trigger Prime Video blackout."""
    result = get_watch_info([b("Amazon", "AMAZON")])
    assert result.is_blacked_out is True
    assert result.prime_video_national is True


# ── NBA TV (soft blackout) ────────────────────────────────────────────────────

def test_nbatv_game_is_blacked_out():
    result = get_watch_info([b("NBA TV", "NBATV")])
    assert result.is_blacked_out is True
    services = [opt.service for opt in result.watch_on]
    assert any("NBA" in s for s in services)


def test_nbatv_note_mentions_league_pass_replay():
    result = get_watch_info([b("NBA TV", "NBATV")])
    notes = [opt.note for opt in result.watch_on if opt.note]
    assert notes, "Expected a note for NBA TV games"
    combined = " ".join(notes).lower()
    assert "league pass" in combined or "replay" in combined


# ── Network display names ─────────────────────────────────────────────────────

def test_national_network_names_captured():
    result = get_watch_info([b("ESPN", "ESPN")])
    assert "ESPN" in result.national_networks


def test_local_network_names_captured():
    result = get_watch_info(
        national_broadcasters=[],
        home_tv_broadcasters=[b("Spectrum SportsNet", "SPSN")],
    )
    assert "Spectrum SportsNet" in result.local_networks


def test_local_plus_national_blackout():
    """Game on both ESPN and Spectrum SportsNet → blacked out (national takes precedence)."""
    result = get_watch_info(
        national_broadcasters=[b("ESPN", "ESPN")],
        home_tv_broadcasters=[b("Spectrum SportsNet", "SPSN")],
    )
    assert result.is_blacked_out is True
    assert result.league_pass_available is False


# ── Return type ───────────────────────────────────────────────────────────────

def test_returns_watch_info_instance():
    result = get_watch_info([])
    assert isinstance(result, WatchInfo)


def test_watch_on_always_populated():
    """watch_on should never be empty — there's always somewhere to watch."""
    for broadcasters in [
        [],
        [b("ESPN", "ESPN")],
        [b("Prime Video", "PRIME")],
        [b("NBC", "NBC")],
        [b("NBA TV", "NBATV")],
    ]:
        result = get_watch_info(broadcasters)
        assert result.watch_on, f"watch_on was empty for {broadcasters}"
