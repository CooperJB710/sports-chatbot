#!/usr/bin/env python3
"""
Extract:   download Kaggle NBA team stats CSV
Transform: tidy col names, cast numerics, drop null rows
Load:      write to a local SQLite database (nba_stats.db)
"""
import os, subprocess, zipfile, sqlite3, pandas as pd

DATA_ZIP   = "nba.zip"
DATA_CSV   = "NBA Team Stats.csv"
DB_FILE    = "../nba_stats.db"
KAGGLE_DS  = "supremeleaf/nba-regular-season-team-stats-2001-2023"

def download():
    if os.path.exists(DATA_ZIP):
        return
    try:
        subprocess.run(
            ["kaggle", "datasets", "download", "-d", KAGGLE_DS, "-p", ".", "--unzip", "--quiet"],
            check=True)
    except Exception as e:
        raise RuntimeError(
            "Kaggle download failed. Did you run `pip install kaggle` and place kaggle.json in ~/.kaggle?") from e

def transform():
    df = pd.read_csv(DATA_CSV)
    df.columns = df.columns.str.lower().str.replace(" ", "_")
    df = df.dropna(subset=["team", "season"])
    numeric_cols = df.select_dtypes(include="object").columns[df.apply(lambda s: s.str.replace('.','',1).str.isdigit()).all()]
    df[numeric_cols] = df[numeric_cols].apply(pd.to_numeric, errors="coerce")
    return df

def load(df):
    conn = sqlite3.connect(DB_FILE)
    df.to_sql("team_stats", conn, if_exists="replace", index=False)
    conn.close()

if __name__ == "__main__":
    download()
    df = transform()
    load(df)
    print("✅ ETL complete – nba_stats.db ready.")
