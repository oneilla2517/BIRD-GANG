#!/usr/bin/env python3
"""
Pulls current-season standings AND prior-season history from ESPN's fantasy
football API (via the espn_api library) and writes it all to data.json,
which index.html reads on page load.

Required environment variables:
  ESPN_LEAGUE_ID   - the number in your league URL, e.g. 899513
  ESPN_SEASON      - current season, e.g. 2026
  ESPN_S2          - cookie value (private leagues only)
  ESPN_SWID        - cookie value, including the curly braces (private leagues only)

Public league? Just leave ESPN_S2 / ESPN_SWID unset.

History: the script walks backward season by season (2025, 2024, 2023...)
and stops automatically as soon as a season fails to load — which is what
happens once it reaches a year before the league existed. No need to
configure how far back to go.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone

from espn_api.football import League

# Must match the "team" names used in index.html's `teams` array (t.team),
# mapped to that same team's `id`. Edit this if a team renames itself mid-season.
TEAM_NAME_TO_ID = {
    "seed": "drew",
    "ovo mark": "mark",
    "the manager": "christian",
    "team yahoo": "joey",
    "mr reseed": "steve",
    "sleepystoners": "roldi",
    "adrians astounding team": "papo",
    "walsh my balls": "big",
    "unsolicited dak pics": "willy",
    "team s oneill": "shawno",
    "howie hinkie sixersin6": "deamer",
    "yn nut": "robinson",
}

MAX_SEASONS_BACK = 15  # safety cap so a weird API response can't loop forever


def normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


NORMALIZED_MAP = {normalize(k): v for k, v in TEAM_NAME_TO_ID.items()}


def teams_snapshot(league) -> dict:
    """Build a {internal_id: {...}} dict from a League object's current teams."""
    out = {}
    unmatched = []
    for team in league.teams:
        key = normalize(team.team_name)
        internal_id = NORMALIZED_MAP.get(key)
        if not internal_id:
            unmatched.append(team.team_name)
            continue
        out[internal_id] = {
            "wins": team.wins,
            "losses": team.losses,
            "ties": getattr(team, "ties", 0),
            "pointsFor": round(getattr(team, "points_for", 0), 1),
            # regular-season standing (rank within the league that year)
            "standing": getattr(team, "standing", None),
            # final standing including playoffs, if the season is complete
            # (1 = champion). Falls back to regular-season standing if the
            # library doesn't expose it for a given year.
            "finalStanding": getattr(team, "final_standing", None) or getattr(team, "standing", None),
        }
    if unmatched:
        print(
            f"WARNING ({league.year}): couldn't match these ESPN team names "
            f"to a known team — check for a rename: {unmatched}",
            file=sys.stderr,
        )
    return out


def main():
    league_id = int(os.environ["ESPN_LEAGUE_ID"])
    current_season = int(os.environ.get("ESPN_SEASON", datetime.now().year))
    espn_s2 = os.environ.get("ESPN_S2")
    swid = os.environ.get("ESPN_SWID")

    auth = {}
    if espn_s2 and swid:
        auth = {"espn_s2": espn_s2, "swid": swid}

    print(f"Connecting to league {league_id}, current season {current_season}...", file=sys.stderr)
    current_league = League(league_id=league_id, year=current_season, **auth)
    current_teams = teams_snapshot(current_league)

    history = {}
    year = current_season - 1
    seasons_tried = 0
    while seasons_tried < MAX_SEASONS_BACK:
        seasons_tried += 1
        try:
            print(f"Fetching {year}...", file=sys.stderr)
            past_league = League(league_id=league_id, year=year, **auth)
            snap = teams_snapshot(past_league)
            if not snap:
                print(f"  {year}: no matching teams, stopping history walk.", file=sys.stderr)
                break
            history[str(year)] = snap
            year -= 1
        except Exception as e:
            print(f"  {year}: failed ({e}) — assuming league didn't exist yet, stopping.", file=sys.stderr)
            break

    data = {
        "season": current_season,
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "teams": current_teams,
        "history": history,
    }

    out_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data.json")
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Wrote {out_path}: {len(current_teams)} current teams, {len(history)} historical seasons.")


if __name__ == "__main__":
    main()
