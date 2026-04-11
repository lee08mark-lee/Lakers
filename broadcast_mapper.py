"""
broadcast_mapper.py

Maps NBA broadcast network data to streaming services for a user in Phoenix, AZ
with NBA League Pass via Amazon Prime.

Blackout rules:
- Phoenix is NOT in the Lakers' local TV market → no local-market blackout
- Any nationally televised game IS blacked out on League Pass live
- Local-only games (Spectrum SportsNet) → League Pass is available
"""

from dataclasses import dataclass, field

# All abbreviations that trigger a League Pass blackout
BLACKOUT_ABBREVIATIONS: set[str] = {
    "ESPN", "ESPN2", "ABC",           # Disney/ESPN rights
    "NBC", "NBCSP",                   # NBC/Peacock rights
    "PEACOCK",                        # Peacock streaming-native
    "PRIME", "AMAZON", "AMZN",        # Amazon Prime Video rights
    "NBATV",                          # NBA TV (soft blackout — see note)
}

# Network abbreviation → where this user should watch
NETWORK_TO_STREAMING: dict[str, dict] = {
    "ESPN": {
        "service": "ESPN (ESPN app)",
        "url": "https://www.espn.com/watch/",
        "note": None,
    },
    "ESPN2": {
        "service": "ESPN2 (ESPN app)",
        "url": "https://www.espn.com/watch/",
        "note": None,
    },
    "ABC": {
        "service": "ABC (ESPN app — ABC simulcast)",
        "url": "https://www.espn.com/watch/",
        "note": None,
    },
    "NBC": {
        "service": "NBC (Peacock)",
        "url": "https://www.peacocktv.com/",
        "note": None,
    },
    "NBCSP": {
        "service": "NBC Sports (Peacock)",
        "url": "https://www.peacocktv.com/",
        "note": None,
    },
    "PEACOCK": {
        "service": "Peacock",
        "url": "https://www.peacocktv.com/",
        "note": None,
    },
    "PRIME": {
        "service": "Amazon Prime Video",
        "url": "https://www.amazon.com/primevideo/",
        "note": (
            "This game is on Prime Video nationally. "
            "Watch directly in the Prime Video app — "
            "NOT through the League Pass channel."
        ),
    },
    "AMAZON": {
        "service": "Amazon Prime Video",
        "url": "https://www.amazon.com/primevideo/",
        "note": (
            "This game is on Prime Video nationally. "
            "Watch directly in the Prime Video app — "
            "NOT through the League Pass channel."
        ),
    },
    "AMZN": {
        "service": "Amazon Prime Video",
        "url": "https://www.amazon.com/primevideo/",
        "note": (
            "This game is on Prime Video nationally. "
            "Watch directly in the Prime Video app — "
            "NOT through the League Pass channel."
        ),
    },
    "NBATV": {
        "service": "NBA TV (NBA App)",
        "url": "https://www.nba.com/watch/",
        "note": (
            "NBA TV games are technically blacked out on League Pass live, "
            "but may be watchable via the NBA App or as a League Pass add-on. "
            "League Pass replay is available after the game."
        ),
    },
}


@dataclass
class WatchOption:
    service: str
    url: str
    note: str | None = None


@dataclass
class WatchInfo:
    is_blacked_out: bool
    league_pass_available: bool
    watch_on: list[WatchOption] = field(default_factory=list)
    # Display names of the broadcasting networks (e.g. ["ESPN", "Spectrum SportsNet"])
    national_networks: list[str] = field(default_factory=list)
    local_networks: list[str] = field(default_factory=list)
    # True only for the Amazon-national-game edge case
    prime_video_national: bool = False


def get_watch_info(
    national_broadcasters: list[dict],
    home_tv_broadcasters: list[dict] | None = None,
    away_tv_broadcasters: list[dict] | None = None,
) -> WatchInfo:
    """
    Determine where to watch a Lakers game for a Phoenix, AZ viewer
    with NBA League Pass via Amazon Prime.

    Parameters
    ----------
    national_broadcasters : list of broadcaster dicts from the NBA API
        Each dict has at minimum 'broadcasterDisplay' and 'broadcasterAbbreviation'.
    home_tv_broadcasters, away_tv_broadcasters : RSN broadcaster lists (optional)
    """
    home_tv_broadcasters = home_tv_broadcasters or []
    away_tv_broadcasters = away_tv_broadcasters or []

    # Collect national network display names and abbreviations
    national_names: list[str] = []
    national_abbrevs: set[str] = set()
    for b in national_broadcasters:
        display = b.get("broadcasterDisplay", "").strip()
        abbrev = b.get("broadcasterAbbreviation", "").strip().upper()
        if display:
            national_names.append(display)
        if abbrev:
            national_abbrevs.add(abbrev)

    # Collect local RSN names for display (Spectrum SportsNet, Bally Sports AZ, etc.)
    local_names: list[str] = []
    for b in home_tv_broadcasters + away_tv_broadcasters:
        display = b.get("broadcasterDisplay", "").strip()
        if display and display not in local_names:
            local_names.append(display)

    # Which blackout-triggering networks are present?
    blacking_abbrevs = national_abbrevs & BLACKOUT_ABBREVIATIONS

    if not blacking_abbrevs:
        # No national broadcaster → League Pass available (Phoenix, no local blackout)
        return WatchInfo(
            is_blacked_out=False,
            league_pass_available=True,
            watch_on=[
                WatchOption(
                    service="NBA League Pass (via Amazon Prime)",
                    url="https://www.amazon.com/primevideo/",
                )
            ],
            national_networks=national_names,
            local_networks=local_names,
        )

    # Build streaming options, deduplicating by service name
    seen_services: set[str] = set()
    watch_options: list[WatchOption] = []
    prime_national = False

    for abbrev in sorted(blacking_abbrevs):  # sorted for determinism
        mapping = NETWORK_TO_STREAMING.get(abbrev)
        if not mapping:
            continue
        service_name = mapping["service"]
        if service_name not in seen_services:
            seen_services.add(service_name)
            watch_options.append(WatchOption(
                service=service_name,
                url=mapping["url"],
                note=mapping["note"],
            ))
        if abbrev in {"PRIME", "AMAZON", "AMZN"}:
            prime_national = True

    return WatchInfo(
        is_blacked_out=True,
        league_pass_available=False,
        watch_on=watch_options,
        national_networks=national_names,
        local_networks=local_names,
        prime_video_national=prime_national,
    )
