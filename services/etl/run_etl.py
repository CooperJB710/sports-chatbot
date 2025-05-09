#!/usr/bin/env python3
"""
ETL – stats.nba.com via nba_api ➜ SQLite (+ legacy CSV)

Example (2023-24 season):
    python run_etl.py 2024
"""
import os, sys, sqlite3, pandas as pd
from nba_api.stats.static import teams as static_teams
from nba_api.stats.endpoints import leaguegamefinder

# ── choose season string like "2023-24" ───────────────────────────────
SEASON_END = int(sys.argv[1]) if len(sys.argv) > 1 else 2024
SEASON_STR = f"{SEASON_END-1}-{str(SEASON_END)[-2:]}"          # '2023-24'

ROOT     = os.path.abspath(os.path.dirname(__file__))
DB_FILE  = os.path.join(ROOT, "nba_stats.db")
CSV_FILE = os.path.join(ROOT, "NBA Team Stats.csv")

# ── 1.  Teams table ──────────────────────────────────────────────────
teams_df = (
    pd.DataFrame(static_teams.get_teams())
      .rename(columns={
          "id": "team_id",
          "full_name": "team_name",
          "abbreviation": "abbrev",
          "city": "city",
          "conference": "conference",
          "division": "division",
      })
)

# ── 2.  Games table (one row per game) ───────────────────────────────
gf = leaguegamefinder.LeagueGameFinder(
    season_nullable      = SEASON_STR,
    season_type_nullable = "Regular Season",
    league_id_nullable   = "00",
)
df_raw = gf.get_data_frames()[0][
    ["GAME_ID", "GAME_DATE", "TEAM_ID", "PTS", "MATCHUP"]
]

records = []
for gid, grp in df_raw.groupby("GAME_ID"):
    if len(grp) != 2:            # should always be 2
        continue
    a, b          = grp.iloc[0], grp.iloc[1]
    home, away    = (a, b) if "vs." in a.MATCHUP else (b, a)
    records.append({
        "game_id":    gid,
        "date":       home.GAME_DATE,
        "home_id":    int(home.TEAM_ID),
        "away_id":    int(away.TEAM_ID),
        "home_score": int(home.PTS),
        "away_score": int(away.PTS),
        "season":     SEASON_END,
    })

games_df = pd.DataFrame(records)

# ── 3.  Optional legacy CSV ──────────────────────────────────────────
if os.path.exists(CSV_FILE):
    csv_df = pd.read_csv(CSV_FILE)

    csv_df = csv_df.rename(columns={
        "Team":         "team",
        "Season":       "season",
        "PTS Per Game": "pts",
        "FG%":          "fg%",
        "TRB":          "trb",
    })

    csv_df.columns = (
        csv_df.columns
              .str.strip()
              .str.lower()
              .str.replace(r"\s+", "_", regex=True)
    )

    for c in csv_df.columns:
        if csv_df[c].dtype == object:
            csv_df[c] = csv_df[c].str.rstrip("%").replace("", pd.NA)
        csv_df[c] = pd.to_numeric(csv_df[c], errors="ignore")

    csv_df = csv_df.dropna(subset=["team", "season"]).reset_index(drop=True)
else:
    csv_df = pd.DataFrame()

# ── 4.  Write SQLite file ────────────────────────────────────────────
with sqlite3.connect(DB_FILE) as conn:
    teams_df.to_sql("teams", conn, if_exists="replace", index=False)
    games_df.to_sql("games", conn, if_exists="replace", index=False)
    if not csv_df.empty:
        csv_df.to_sql("team_stats", conn, if_exists="replace", index=False)

print(
    f"✅  {len(teams_df)} teams, {len(games_df)} games"
    + (f', {len(csv_df)} CSV rows' if not csv_df.empty else '')
    + f" ➜  {DB_FILE}"
)
