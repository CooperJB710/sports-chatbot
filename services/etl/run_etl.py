#!/usr/bin/env python3
import os, sys, sqlite3, pandas as pd
from nba_api.stats.static import teams as static_teams
from nba_api.stats.endpoints import leaguegamefinder

ROOT=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_FILE=os.path.join(ROOT,"nba_stats.db")
CSV_FILE=os.path.join(ROOT,"NBA Team Stats.csv")

SEASON_END=int(sys.argv[1]) if len(sys.argv)>1 else 2024
SEASON_STR=f"{SEASON_END-1}-{str(SEASON_END)[-2:]}"  # e.g. 2023-24

teams_df=pd.DataFrame(static_teams.get_teams()).rename(columns={
    "id":"team_id","full_name":"team_name","abbreviation":"abbrev",
    "city":"city","conference":"conference","division":"division"})

gf=leaguegamefinder.LeagueGameFinder(
    season_nullable=SEASON_STR,season_type_nullable="Regular Season")
raw=gf.get_data_frames()[0][["GAME_ID","GAME_DATE","TEAM_ID","PTS","MATCHUP"]]

recs=[]
for gid,grp in raw.groupby("GAME_ID"):
    a,b=grp.iloc[0],grp.iloc[1]
    home,away=(a,b) if "vs." in a.MATCHUP else (b,a)
    recs.append({"game_id":gid,"date":home.GAME_DATE,
                 "home_id":int(home.TEAM_ID),"away_id":int(away.TEAM_ID),
                 "home_score":int(home.PTS),"away_score":int(away.PTS),
                 "season":SEASON_END})
games_df=pd.DataFrame(recs)

with sqlite3.connect(DB_FILE) as c:
    teams_df.to_sql("teams",c,if_exists="replace",index=False)
    games_df.to_sql("games",c,if_exists="replace",index=False)

print(f"DB written to {DB_FILE}")
