# Bird Gang — Live ESPN Setup

The site works fine as a static file with no setup at all. This part is
optional — it makes the "2026 Divisions" standings update automatically
from your real ESPN league instead of showing 0-0-0.

## 1. Put this on GitHub

Create a repo (private or public, doesn't matter) and upload everything in
this folder, keeping the folder structure intact:

```
index.html
data.json          (starter file — gets overwritten automatically)
scripts/fetch_espn.py
.github/workflows/update-espn.yml
```

## 2. Turn on GitHub Pages

Repo → Settings → Pages → Source: "Deploy from a branch" → branch `main`,
folder `/ (root)`. GitHub gives you a URL like
`https://yourname.github.io/bird-gang/` — that's the link you send the guys.

## 3. Find your League ID

Go to your league on ESPN. The URL looks like:

```
https://fantasy.espn.com/football/team?leagueId=899513&seasonId=2026
```

`899513` is your League ID.

## 4. Get your espn_s2 and SWID cookies (private leagues only)

Since your league is invite-only, ESPN needs these two cookies to prove
you're logged in. **Treat them like a password** — anyone with them can act
as you on ESPN. That's exactly why they go into GitHub Secrets (encrypted,
never visible in the site's code) instead of anywhere in index.html.

1. Log into fantasy.espn.com in Chrome
2. Open DevTools (right-click → Inspect) → **Application** tab → **Cookies** → `https://fantasy.espn.com`
3. Find `espn_s2` — copy the whole value (it's long)
4. Find `SWID` — copy the value **including the curly braces**, e.g. `{ABC123-...}`

## 5. Add secrets to your GitHub repo

Repo → Settings → Secrets and variables → Actions:

**Secrets** (click "New repository secret" for each):
- `ESPN_LEAGUE_ID` — your league ID from step 3
- `ESPN_S2` — from step 4
- `ESPN_SWID` — from step 4

**Variables** (same page, "Variables" tab):
- `ESPN_SEASON` — e.g. `2026`

## 6. Run it

Actions tab → "Update ESPN standings" → "Run workflow" to test it
immediately. After that it runs automatically every 2 hours on game days
(Sun/Mon/Thu) and commits the fresh `data.json`, which the live site picks
up on next page load.

Want a different schedule? Edit the `cron:` line in
`.github/workflows/update-espn.yml` — every line runs on GitHub's clock in
UTC.

## If a team ever renames itself on ESPN

`scripts/fetch_espn.py` matches ESPN team names to your site's teams by
name. If someone renames their team mid-season, add the new name to the
`TEAM_NAME_TO_ID` dictionary at the top of that file so it keeps matching.
