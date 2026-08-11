#!/usr/bin/env python3
"""
Pulls current + historical fantasy football data from ESPN (via espn_api)
and writes it to data.json for index.html to render:
  - current season standings
  - prior season final standings (walks backward until a season fails to load)
  - every regular-season + playoff box score, every week, every season
    (used to compute single-game records, season scoring leaders, and
    playoff win totals)
  - playoff bracket matchups per season

Required environment variables:
  ESPN_LEAGUE_ID   - the number in your league URL, e.g. 899513
  ESPN_SEASON      - current season, e.g. 2026
  ESPN_S2          - cookie value (private leagues only)
  ESPN_SWID        - cookie value, including the curly braces (private leagues only)

History: walks backward (2025, 2024, 2023...) and stops automatically once a
season fails to load — no need to configure how far back to go.
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

MAX_SEASONS_BACK = 15   # safety cap on how many years to walk backward
MAX_WEEKS = 18          # safety cap on how many weeks to check per season


def normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


NORMALIZED_MAP = {normalize(k): v for k, v in TEAM_NAME_TO_ID.items()}


def id_for(team) -> str | None:
    if team is None:
        return None
    return NORMALIZED_MAP.get(normalize(getattr(team, "team_name", "")))


def teams_snapshot(league) -> dict:
    """Build a {internal_id: {...}} dict from a League object's current teams."""
    out = {}
    unmatched = []
    for team in league.teams:
        internal_id = id_for(team)
        if not internal_id:
            unmatched.append(team.team_name)
            continue
        out[internal_id] = {
            "wins": team.wins,
            "losses": team.losses,
            "ties": getattr(team, "ties", 0),
            "pointsFor": round(getattr(team, "points_for", 0), 1),
            "standing": getattr(team, "standing", None),
            "finalStanding": getattr(team, "final_standing", None) or getattr(team, "standing", None),
        }
    if unmatched:
        print(
            f"WARNING ({league.year}): couldn't match these ESPN team names "
            f"to a known team — check for a rename: {unmatched}",
            file=sys.stderr,
        )
    return out


def weekly_data(league, season: int):
    """Walk every week of a season's box scores. Returns (scores, bracket)."""
    reg_weeks = getattr(league.settings, "reg_season_count", 14)
    scores = []
    bracket = []

    for week in range(1, MAX_WEEKS + 1):
        try:
            box_scores = league.box_scores(week)
        except Exception as e:
            print(f"    week {week}: stopped ({e})", file=sys.stderr)
            break
        if not box_scores:
            break

        is_playoff = week > reg_weeks
        week_matchups = []

        for m in box_scores:
            home, away = getattr(m, "home_team", None), getattr(m, "away_team", None)
            home_score, away_score = getattr(m, "home_score", None), getattr(m, "away_score", None)
            hid, aid = id_for(home), id_for(away)

            if hid and home_score is not None:
                scores.append({
                    "season": season, "week": week, "teamId": hid, "score": round(home_score, 1),
                    "oppId": aid, "oppScore": round(away_score, 1) if away_score is not None else None,
                    "isPlayoff": is_playoff,
                })
            if aid and away_score is not None:
                scores.append({
                    "season": season, "week": week, "teamId": aid, "score": round(away_score, 1),
                    "oppId": hid, "oppScore": round(home_score, 1) if home_score is not None else None,
                    "isPlayoff": is_playoff,
                })

            if is_playoff and hid and aid and home_score is not None and away_score is not None:
                week_matchups.append({
                    "teamId": hid, "score": round(home_score, 1),
                    "oppId": aid, "oppScore": round(away_score, 1),
                    "winnerId": hid if home_score > away_score else aid,
                })

        if is_playoff and week_matchups:
            bracket.append({"week": week, "matchups": week_matchups})

    return scores, bracket


def main():
    league_id = int(os.environ["ESPN_LEAGUE_ID"])
    current_season = int(os.environ.get("ESPN_SEASON", datetime.now().year))
    espn_s2 = os.environ.get("ESPN_S2")
    swid = os.environ.get("ESPN_SWID")

    auth = {}
    if espn_s2 and swid:
        auth = {"espn_s2": espn_s2, "swid": swid}

    all_weekly_scores = []
    all_brackets = {}
    history = {}

    print(f"Connecting to league {league_id}, current season {current_season}...", file=sys.stderr)
    current_league = League(league_id=league_id, year=current_season, **auth)
    current_teams = teams_snapshot(current_league)
    cur_scores, cur_bracket = weekly_data(current_league, current_season)
    all_weekly_scores += cur_scores
    if cur_bracket:
        all_brackets[str(current_season)] = cur_bracket

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
            scores, bracket = weekly_data(past_league, year)
            all_weekly_scores += scores
            if bracket:
                all_brackets[str(year)] = bracket
            year -= 1
        except Exception as e:
            print(f"  {year}: failed ({e}) — assuming league didn't exist yet, stopping.", file=sys.stderr)
            break

    data = {
        "season": current_season,
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "teams": current_teams,
        "history": history,
        "weeklyScores": all_weekly_scores,
        "playoffBrackets": all_brackets,
    }

    out_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data.json")
    with open(out_path, "w") as f:
        json.dump(data, f, indent=2)

    print(
        f"Wrote {out_path}: {len(current_teams)} current teams, {len(history)} historical "
        f"seasons, {len(all_weekly_scores)} weekly score entries, "
        f"{sum(len(b) for b in all_brackets.values())} playoff-round records."
    )


if __name__ == "__main__":
    main()
