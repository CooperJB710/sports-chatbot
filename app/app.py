import os, re, sqlite3, requests, dotenv
from flask import Flask, request, jsonify

dotenv.load_dotenv()
API_KEY   = os.getenv("TSD_KEY", "3")  # default free key
DB_PATH   = os.path.join(os.path.dirname(__file__), "..", "nba_stats.db")
BASE_URL  = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}"

app = Flask(__name__)

def query_local(team:str, season:int):
    q = """
        SELECT pts, fgm, fga, fgp, ast, trb, opp_pts
        FROM team_stats
        WHERE team LIKE ? AND season = ?
    """
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(q, (f"%{team}%", season)).fetchone()
    return row and dict(zip(
        ["PTS", "FGM", "FGA", "FG%", "AST", "REB", "OPP_PTS"], row))

def query_tsdb(endpoint:str, **params):
    r = requests.get(f"{BASE_URL}/{endpoint}.php", params=params, timeout=10)
    r.raise_for_status()
    return r.json()

@app.post("/chat")
def chat():
    question = request.json.get("question","").lower()
    try:
        # simple heuristics – extend with NLP later
        if "average points" in question:
            m = re.search(r"(\d{4})", question)
            season = int(m.group(1)) if m else 2023
            team  = re.sub(r"[^\w\s]", "", question.split("average points")[-1]).strip()
            stats = query_local(team, season)
            if stats:
                return jsonify(answer=f"{team.title()} averaged {stats['PTS']} PPG in {season}.")
            return jsonify(answer="Sorry, I don't have that season in the local database.")

        if "last game" in question or "recent result" in question:
            team = question.split()[-1]
            data = query_tsdb("eventslast", id=133602)  # replace with lookup via searchteams
            last = data["results"][0]
            return jsonify(answer=f"{last['strEvent']} ended {last['intHomeScore']}-{last['intAwayScore']} on {last['dateEvent']}.")

        # fallback
        return jsonify(answer="I'm not sure – try asking about team averages or recent results.")
    except Exception as e:
        return jsonify(error=str(e)), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
