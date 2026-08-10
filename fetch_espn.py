#!/usr/bin/env python3
"""
Pulls current-season standings from ESPN's fantasy football API and writes
them to data.json, which index.html reads on page load to show live records.

Required environment variables:
  ESPN_LEAGUE_ID   - the number in your league URL, e.g. 899513
  ESPN_SEASON      - e.g. 2026
  ESPN_S2          - cookie value (private leagues only)
  ESPN_SWID        - cookie value, including the curly braces (private leagues only)

Public league? Just leave ESPN_S2 / ESPN_SWID unset.
"""
import json
import os
import re
import sys
from datetime import datetime, timezone

import requests

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


def normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


NORMALIZED_MAP = {normalize(k): v for k, v in TEAM_NAME_TO_ID.items()}


def fetch_league(league_id: str, season: str, espn_s2: str | None, swid: str | None) -> dict:
    url = (
        f"https://fantasy.espn.com/apis/v3/games/ffl/seasons/{season}"
        f"/segments/0/leagues/{league_id}"
    )
    params = {"view": ["mTeam", "mStandings"]}
    cookies = {}
    if espn_s2 and swid:
        cookies = {"espn_s2": espn_s2, "SWID": swid}

    resp = requests.get(url, params=params, cookies=cookies, timeout=20)
    resp.raise_for_status()
    return resp.json()


def build_data_json(league_json: dict, season: str) -> dict:
    teams_out = {}
    unmatched = []

    for team in league_json.get("teams", []):
        # ESPN has used both a single "name" field and separate
        # "location" + "nickname" fields across API versions — try both.
        full_name = team.get("name")
        if not full_name:
            full_name = f'{team.get("location", "")} {team.get("nickname", "")}'.strip()

        key = normalize(full_name)
        internal_id = NORMALIZED_MAP.get(key)
        if not internal_id:
            unmatched.append(full_name)
            continue

        record = team.get("record", {}).get("overall", {})
        teams_out[internal_id] = {
            "wins": record.get("wins", 0),
            "losses": record.get("losses", 0),
            "ties": record.get("ties", 0),
            "pointsFor": record.get("pointsFor", 0),
            "standing": team.get("playoffSeed") or team.get("divisionId"),
        }

    if unmatched:
        print(
            "WARNING: could not match these ESPN team names to a known team "
            f"— check for a rename: {unmatched}",
            file=sys.stderr,
        )

    return {
        "season": int(season),
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "teams": teams_out,
    }


def main():
    league_id = os.environ["ESPN_LEAGUE_ID"]
    season = os.environ.get("ESPN_SEASON", str(datetime.now().year))
    espn_s2 = os.environ.get("ESPN_S2")
    swid = os.environ.get("ESPN_SWID")

    league_json = fetch_league(league_id, season, espn_s2, swid)
    data = build_data_json(league_json, season)

    out_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data.json")
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Wrote {out_path} with {len(data['teams'])} teams matched.")


if __name__ == "__main__":
    main()
