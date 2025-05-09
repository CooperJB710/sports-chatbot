#!/usr/bin/env python3
"""
ETL script to build the local NBA stats database from external sources.
- Extracts data from the nba_api (teams, games, scoring leaders) for a given season.
- Optionally loads additional team stats from an external CSV file ("NBA Team Stats.csv").
- Transforms the data into a consistent format.
- Loads the data into a SQLite database (nba_stats.db).

Usage:
    python run_etl.py [SEASON_END_YEAR]
Example:
    python run_etl.py 2024   # Builds data for the 2023-24 season
"""
import os, sys, sqlite3
import pandas as pd
from nba_api.stats.static import teams as static_teams
from nba_api.stats.endpoints import leaguegamefinder, leagueleaders

# Determine which season to fetch (defaults to 2024 if not specified)
SEASON_END = int(sys.argv[1]) if len(sys.argv) > 1 else 2024
SEASON_STR = f"{SEASON_END-1}-{str(SEASON_END)[-2:]}"  # e.g., 2024 -> "2023-24"

# File paths
ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
DB_FILE = os.path.join(ROOT_DIR, "nba_stats.db")
CSV_FILE = os.path.join(ROOT_DIR, "NBA Team Stats.csv")

# 1. Extract – NBA teams metadata
teams_df = pd.DataFrame(static_teams.get_teams())
teams_df = teams_df.rename(columns={
    "id": "team_id",
    "full_name": "team_name",
    "abbreviation": "abbrev",
    "city": "city",
    "conference": "conference",
    "division": "division",
})

# 2. Extract – Regular season games (combine into one row per game)
gf = leaguegamefinder.LeagueGameFinder(
    season_nullable=SEASON_STR,
    season_type_nullable="Regular Season",
    league_id_nullable="00"
)
games_raw = gf.get_data_frames()[0][["GAME_ID", "GAME_DATE", "TEAM_ID", "PTS", "MATCHUP"]]

# Transform games_raw to a games_df with one record per game (home/away split)
records = []
for game_id, grp in games_raw.groupby("GAME_ID"):
    if len(grp) != 2:
        continue  # skip if not exactly two team entries (shouldn't happen for completed games)
    team_a, team_b = grp.iloc[0], grp.iloc[1]
    # Determine home vs away by checking 'vs.' in the matchup string
    home_rec, away_rec = (team_a, team_b) if "vs." in team_a.MATCHUP else (team_b, team_a)
    records.append({
        "game_id": game_id,
        "date": home_rec.GAME_DATE,
        "home_id": int(home_rec.TEAM_ID),
        "away_id": int(away_rec.TEAM_ID),
        "home_score": int(home_rec.PTS),
        "away_score": int(away_rec.PTS),
        "season": SEASON_END
    })
games_df = pd.DataFrame(records)

# 3. Extract – Season scoring leaders (as an example of another API call)
leaders_df = leagueleaders.LeagueLeaders(
    season=SEASON_STR,
    stat_category_abbreviation="PTS",
    league_id="00",
    season_type="Regular Season",
).get_data_frames()[0]

# 4. (Optional) Extract – Team average stats from CSV if available
if os.path.exists(CSV_FILE):
    csv_df = pd.read_csv(CSV_FILE)
    # Rename certain columns for consistency
    csv_df = csv_df.rename(columns={
        "Team": "team",
        "Season": "season",
        "PTS Per Game": "pts",
        "FG%": "fg%",
        "TRB": "trb",
        # add more renames if needed...
    })
    # Standardize column names (snake_case)
    csv_df.columns = (csv_df.columns
                      .str.strip()
                      .str.lower()
                      .str.replace(r"\s+", "_", regex=True))
    # Convert percentage strings and empty strings to numeric/NaN
    for col in csv_df.columns:
        if csv_df[col].dtype == object:
            csv_df[col] = csv_df[col].str.rstrip("%").replace("", pd.NA)
            csv_df[col] = pd.to_numeric(csv_df[col], errors="ignore")
    # Drop rows missing critical fields (team or season)
    csv_df = csv_df.dropna(subset=["team", "season"]).reset_index(drop=True)
else:
    csv_df = pd.DataFrame()

# 5. Load – Write all extracted data to the SQLite database
with sqlite3.connect(DB_FILE) as conn:
    teams_df.to_sql("teams", conn, if_exists="replace", index=False)
    games_df.to_sql("games", conn, if_exists="replace", index=False)
    leaders_df.to_sql("season_leaders", conn, if_exists="replace", index=False)
    if not csv_df.empty:
        csv_df.to_sql("team_stats", conn, if_exists="replace", index=False)

print(f"✅ ETL complete. Saved {len(teams_df)} teams, {len(games_df)} games" +
      (" and team_stats." if not csv_df.empty else "."))
