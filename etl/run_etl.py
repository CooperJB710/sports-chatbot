#!/usr/bin/env python3
"""
Transform: Clean column names, cast numeric values, drop null rows
Load:      Write to a local SQLite database (nba_stats.db)
"""
import os
import sqlite3
import pandas as pd

DATA_CSV = "NBA Team Stats.csv"
# DB_FILE = "nba_stats.db"
DB_FILE = os.path.join(os.path.dirname(__file__), "nba_stats.db")


def transform():
    # Read CSV and clean data
    df = pd.read_csv(DATA_CSV)

    # Standardize column names
    df.columns = df.columns.str.lower().str.replace(" ", "_")
    for col in df.columns:
        if df[col].dtype == "object":
            df[col] = pd.to_numeric(df[col].str.rstrip("%"), errors="coerce")

    # Drop rows with missing team/season
    df = df.dropna(subset=["team", "season"])

    # Identify numeric columns (alternative approach)
    numeric_cols = []
    for col in df.select_dtypes(include="object").columns:
        try:
            # Try converting to numeric
            pd.to_numeric(df[col].str.replace('%', ''), errors='raise')
            numeric_cols.append(col)
        except:
            continue

    # Convert identified numeric columns
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col].str.replace('%', ''), errors='coerce')

    return df


def load(df):
    with sqlite3.connect(DB_FILE) as conn:
        df.to_sql("team_stats", conn, if_exists="replace", index=False)



if __name__ == "__main__":
    if not os.path.exists(DATA_CSV):
        print(f"❌ Error: '{DATA_CSV}' not found in the current directory.")
    else:
        try:
            df = transform()
            load(df)
            print(f"✅ ETL complete – '{DB_FILE}' created with 'team_stats' table.")
            print(f"Columns created: {df.columns.tolist()}")
        except Exception as e:
            print(f"❌ Error during ETL: {str(e)}")
