#!/usr/bin/env python3
"""
Flask NBA Stats Bot
------------------

 • GET  / and /healthz – lightweight 200-OK probes so Cloud Run (or any LB)
   can verify the container is alive.
 • POST /chat        – JSON  {"question": "..."}  →  {"answer": "..."}

The service reads a local SQLite DB ( nba_stats.db ) that the ETL step writes.
"""

from __future__ import annotations
import os, re, sqlite3, json, pathlib
from flask import Flask, request, jsonify

# --------------------------------------------------------------------------- #
#  Paths & Flask setup
# --------------------------------------------------------------------------- #
APP_DIR = pathlib.Path(__file__).resolve().parent
DB_PATH = APP_DIR / "nba_stats.db"                 # →  services/api/nba_stats.db
app     = Flask(__name__)

# --------------------------------------------------------------------------- #
#  Team “fuzzy” aliases  (feel free to extend)
# --------------------------------------------------------------------------- #
ALIASES: dict[str, str] = {
    "wiz": "washington wizards", "wantnos": "washington wizards",
    "lakers": "los angeles lakers",
    "celtics": "boston celtics", "celllics": "boston celtics",
    "warriors": "golden state warriors",
    "heat": "miami heat",
}

# --------------------------------------------------------------------------- #
#  Build {search_key → team_id} once at start-up
# --------------------------------------------------------------------------- #
def _build_team_map() -> dict[str, int]:
    try:
        with sqlite3.connect(DB_PATH) as c:
            rows = c.execute(
                "SELECT team_id, team_name, abbrev, city FROM teams"
            ).fetchall()
    except sqlite3.OperationalError:
        # ETL hasn’t run yet – keep serving health endpoints anyway
        app.logger.warning("⚠️  nba_stats.db missing – /chat will 500 until ETL runs")
        return {}

    mapping: dict[str, int] = {}
    for tid, name, abbr, city in rows:
        tokens = {
            name.lower(),
            abbr.lower(),
            city.lower(),
            f"{city.lower()} {name.split()[-1].lower()}",
        }
        for t in tokens:
            mapping[t] = tid
    return mapping


TEAM_ID = _build_team_map()


def _resolve_team(raw: str) -> int | None:
    """Return team_id for a fuzzy team string or None if unknown."""
    key = ALIASES.get(raw.lower().strip(), raw.lower().strip())
    return TEAM_ID.get(key)


# --------------------------------------------------------------------------- #
#  Small helper queries
# --------------------------------------------------------------------------- #
def _avg_pts(tid: int, season: int) -> float | None:
    sql = """
    WITH pts AS (
        SELECT home_score AS p FROM games WHERE season=? AND home_id=?
        UNION ALL
        SELECT away_score      FROM games WHERE season=? AND away_id=?
    )
    SELECT ROUND(AVG(p), 1) FROM pts;
    """
    with sqlite3.connect(DB_PATH) as c:
        return c.execute(sql, (season, tid, season, tid)).fetchone()[0]


def _last_game(tid: int):
    sql = """
      SELECT date, home_id, away_id, home_score, away_score
      FROM games
      WHERE home_id = ? OR away_id = ?
      ORDER BY date DESC LIMIT 1;
    """
    with sqlite3.connect(DB_PATH) as c:
        return c.execute(sql, (tid, tid)).fetchone()


def _team_name(tid: int) -> str:
    with sqlite3.connect(DB_PATH) as c:
        return c.execute("SELECT team_name FROM teams WHERE team_id=?", (tid,)).fetchone()[0]


# --------------------------------------------------------------------------- #
#  Health-check routes
# --------------------------------------------------------------------------- #
@app.get("/")
def root():
    """Used by Cloud Run default probe (and quick curl tests)."""
    return "OK", 200


@app.get("/healthz")
def healthz():
    """Separate health endpoint (if you later customise / probes)."""
    return "healthy", 200


# --------------------------------------------------------------------------- #
#  /chat  –  main JSON API
# --------------------------------------------------------------------------- #
@app.post("/chat")
def chat():
    data = request.get_json(silent=True) or {}
    question = (data.get("question") or "").lower()

    try:
        # -------- average PPG -----------------------------------------------
        if "average" in question and ("points" in question or "ppg" in question):
            # year – default to most recent if not supplied
            m     = re.search(r"\b(20\d{2})\b", question)
            year  = int(m.group()) if m else sqlite3.connect(DB_PATH) \
                                               .execute("SELECT MAX(season) FROM games").fetchone()[0]
            team_part = re.sub(r"\b(average|points|ppg|\d{4})\b", "", question).strip()
            tid  = _resolve_team(team_part)
            if not tid:
                return jsonify(answer="Team not recognised."), 200
            avg  = _avg_pts(tid, year)
            return jsonify(answer=f"{_team_name(tid)} averaged {avg} PPG in {year}.")
        # -------- last game --------------------------------------------------
        if any(p in question for p in ("last game", "recent result", "last match")):
            trig = next(p for p in ("last game", "recent result", "last match") if p in question)
            tid  = _resolve_team(question.split(trig)[-1])
            if not tid:
                return jsonify(answer="Team not recognised."), 200
            row = _last_game(tid)
            if not row:
                return jsonify(answer="No recent games found."), 200
            date, home, away, hs, as_ = row
            return jsonify(answer=f"🏀 {date}: {_team_name(home)} {hs} – {as_} {_team_name(away)}")
        # -------- fallback ----------------------------------------------------
        return jsonify(
            answer=(
                "Try e.g. 'What did the Lakers average in 2024?' or "
                "'Last game for the Warriors'"
            )
        )
    except json.JSONDecodeError:
        return jsonify(error="Bad JSON"), 400
    except Exception as exc:
        # log for Cloud Run -> Cloud Logging
        app.logger.exception("Unhandled error in /chat")
        return jsonify(error=f"Server error: {exc}"), 500


# --------------------------------------------------------------------------- #
#  Very small landing page so people can test in a browser
# --------------------------------------------------------------------------- #
@app.get("/ui")  # moved to /ui so / stays a pure health-check
def ui():
    return """
<!DOCTYPE html>
<html><head><title>NBA Stats Bot</title>
<meta charset="utf-8">
<style>
 body{font-family:Arial,Helvetica,sans-serif;max-width:750px;margin:0 auto;padding:20px}
 #question{padding:8px;width:320px}button{padding:8px 16px;background:#0066cc;color:#fff;border:0;cursor:pointer}
 button:hover{background:#0052a3}#response{margin-top:20px;padding:15px;border:1px solid #ddd;border-radius:4px;min-height:50px}
 .examples{margin-top:30px;color:#666}
</style></head><body>
<h1>NBA Stats Bot</h1>
<p>Ask about team statistics or recent games.</p>
<input id="question" placeholder="e.g. 'Last game for the Lakers'" size="40">
<button onclick="ask()">Ask</button>
<div id="response"></div>
<div class="examples">
 <p>Try:</p>
 <ul>
  <li>What did the Warriors average in 2022?</li>
  <li>Last game for the Celtics</li>
  <li>Recent result for Miami Heat</li>
 </ul>
</div>
<script>
 async function ask(){
   const q=document.getElementById("question").value.trim();
   if(!q) return;
   const div=document.getElementById("response");
   div.textContent="Thinking…";div.style.color="";
   try{
     const res=await fetch("/chat",{method:"POST",headers:{'Content-Type':'application/json'},
       body:JSON.stringify({question:q})});
     const data=await res.json();
     div.textContent=data.answer||data.error||"Unexpected response";
     if(data.error) div.style.color="red";
   }catch(e){div.textContent="Network error";div.style.color="red";}
 }
 document.getElementById("question")
   .addEventListener("keypress",e=>e.key==="Enter"&&ask());
</script></body></html>
"""


# --------------------------------------------------------------------------- #
#  Local development helper
# --------------------------------------------------------------------------- #
if __name__ == "__main__":  # Enables `python app.py` for quick local test
    port = int(os.getenv("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=True)
