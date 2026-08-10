#!/usr/bin/env python3
"""
Pulls current-season standings from ESPN's fantasy football API (via the
espn_api library) and writes them to data.json, which index.html reads on
page load to show live records.

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


def normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


NORMALIZED_MAP = {normalize(k): v for k, v in TEAM_NAME_TO_ID.items()}


def main():
    league_id = int(os.environ["ESPN_LEAGUE_ID"])
    season = int(os.environ.get("ESPN_SEASON", datetime.now().year))
    espn_s2 = os.environ.get("ESPN_S2")
    swid = os.environ.get("ESPN_SWID")

    kwargs = {"league_id": league_id, "year": season}
    if espn_s2 and swid:
        kwargs["espn_s2"] = espn_s2
        kwargs["swid"] = swid

    print(f"Connecting to league {league_id}, season {season}...", file=sys.stderr)
    league = League(**kwargs)

    teams_out = {}
    unmatched = []

    for team in league.teams:
        key = normalize(team.team_name)
        internal_id = NORMALIZED_MAP.get(key)
        if not internal_id:
            unmatched.append(team.team_name)
            continue

        teams_out[internal_id] = {
            "wins": team.wins,
            "losses": team.losses,
            "ties": getattr(team, "ties", 0),
            "pointsFor": round(getattr(team, "points_for", 0), 1),
            "standing": getattr(team, "standing", None) or getattr(team, "final_standing", None),
        }

    if unmatched:
        print(
            "WARNING: could not match these ESPN team names to a known team "
            f"— check for a rename: {unmatched}",
            file=sys.stderr,
        )

    data = {
        "season": season,
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "teams": teams_out,
    }

    out_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data.json")
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Wrote {out_path} with {len(teams_out)} teams matched.")


if __name__ == "__main__":
    main()
