import os, re, sqlite3, requests, dotenv
from flask import Flask, request, jsonify

dotenv.load_dotenv()
API_KEY = os.getenv("TSD_KEY", "3")  # default free key
DB_PATH = os.path.join(os.path.dirname(__file__), "nba_stats.db")
BASE_URL = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}"

app = Flask(__name__)

# Team name normalization dictionary
TEAM_ALIASES = {
    'wantnos': 'washington wizards',
    'wiz': 'washington wizards',
    'lakers': 'los angeles lakers',
    'celtics': 'boston celtics',
    'celllics': 'boston celtics',  # Added typo handling
    'warriors': 'golden state warriors',
    'heat': 'miami heat',
    # Add more mappings as needed
}



def normalize_team_name(team_name: str) -> str:
    """Normalize team names and handle common aliases/typos"""
    team_name = team_name.lower().strip()
    return TEAM_ALIASES.get(team_name, team_name)


def query_local(team: str, season: int):
    q = """
        SELECT pts, fgm, fga, "fg%", ast, trb
        FROM team_stats
        WHERE team LIKE ? AND season = ?
    """
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(q, (f"%{team}%", season)).fetchone()
    return row and dict(zip(
        ["PTS", "FGM", "FGA", "FG%", "AST", "REB"], row))


def query_tsdb(endpoint: str, **params):
    r = requests.get(f"{BASE_URL}/{endpoint}.php", params=params, timeout=10)
    r.raise_for_status()
    return r.json()


def extract_team_name(question: str, trigger_phrase: str) -> str:
    """Improved team name extraction from question"""
    question_part = question.split(trigger_phrase)[-1]
    # Extract words and filter out non-team words
    team_name = ' '.join([word for word in question_part.split()
                          if word.isalpha()]).strip()
    return normalize_team_name(team_name)


@app.post("/chat")
def chat():
    question = request.json.get("question", "").lower()
    try:
        # Handle average points queries (more flexible matching)
        if "average" in question and ("points" in question or "ppg" in question):
            m = re.search(r"(\d{4})", question)
            season = int(m.group(1)) if m else 2023
            team = extract_team_name(question, "average" if "average" in question else "ppg")

            if len(team) < 3:
                return jsonify(answer="Please provide a full team name")

            stats = query_local(team, season)
            if stats:
                return jsonify(answer=f"In {season}, {team.title()} averaged:\n"
                                      f"• Points: {stats['PTS']} PPG\n"
                                      f"• Field Goal %: {stats['FG%']}\n"
                                      f"• Assists: {stats['AST']}\n"
                                      f"• Rebounds: {stats['REB']}")
            return jsonify(answer=f"Sorry, no stats available for {team.title()} in {season}.")

        # Handle recent game queries
        if any(phrase in question for phrase in ["last game", "recent result", "last match"]):
            trigger = next(phrase for phrase in ["last game", "recent result", "last match"]
                           if phrase in question)
            team_name = extract_team_name(question, trigger)

            if len(team_name) < 3:
                return jsonify(answer="Please provide a full team name")

            # Search for team
            search_data = query_tsdb("searchteams", t=team_name)

            if not search_data.get("teams"):
                suggestions = "Try: Celtics, Lakers, Warriors, Heat, etc."
                return jsonify(answer=f"Team '{team_name.title()}' not found. {suggestions}")

            # Find NBA team
            nba_team = next(
                (team for team in search_data["teams"]
                 if team.get("strLeague") == "NBA"),
                None
            )

            if not nba_team:
                return jsonify(answer=f"'{team_name.title()}' doesn't appear to be an NBA team.")

            # Get last event
            team_id = nba_team["idTeam"]
            events_data = query_tsdb("eventslast", id=team_id)

            if not events_data.get("results"):
                return jsonify(answer=f"No recent games found for {nba_team['strTeam']}.")

            last_game = events_data["results"][0]
            home_team = last_game.get('strHomeTeam', 'Unknown')
            away_team = last_game.get('strAwayTeam', 'Unknown')
            home_score = last_game.get('intHomeScore', '?')
            away_score = last_game.get('intAwayScore', '?')
            date = last_game.get('dateEvent', 'unknown date')

            return jsonify(
                answer=f"🏀 {nba_team['strTeam']}'s Last Game:\n"
                       f"• Matchup: {home_team} vs {away_team}\n"
                       f"• Score: {home_score}-{away_score}\n"
                       f"• Date: {date}"
            )

        # Fallback for unrecognized queries
        return jsonify(
            answer="I can help with:\n"
                   "• Team averages: 'What did the Lakers average in 2020?'\n"
                   "• Recent games: 'Last game for the Warriors'\n\n"
                   "Try one of these formats!"
        )
    except json.JSONDecodeError:
        return jsonify(error="Invalid request format"), 400
    except Exception as e:
        return jsonify(error=f"Unexpected server error: {str(e)}"), 500


@app.get("/")
def home():
    return """
    <!DOCTYPE html>
<html>
<head>
  <title>NBA Stats Bot</title>
  <style>
    body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
    #question { padding: 8px; width: 300px; }
    button { padding: 8px 16px; background: #0066cc; color: white; border: none; cursor: pointer; }
    button:hover { background: #0052a3; }
    #response { margin-top: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 4px; min-height: 50px; }
    .examples { margin-top: 30px; color: #666; }
  </style>
</head>
<body>
  <h1>Welcome to the NBA Stats Bot</h1>
  <p>Ask about team statistics or recent games</p>

  <input id="question" placeholder="e.g. 'Last game for the Lakers'" size="40"/>
  <button onclick="ask()">Ask</button>

  <div id="response"></div>

  <div class="examples">
    <p>Try these examples:</p>
    <ul>
      <li>What did the Warriors average in 2022?</li>
      <li>Last game for the Celtics</li>
      <li>Recent result for Miami Heat</li>
    </ul>
  </div>

  <script>
    async function ask() {
      const q = document.getElementById("question").value;
      if (!q.trim()) return;

      const responseDiv = document.getElementById("response");
      responseDiv.textContent = "Thinking...";
      responseDiv.style.color = "inherit";

      try {
        const res = await fetch("/chat", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ question: q })
        });
        const data = await res.json();

        if (data.answer) {
          responseDiv.textContent = data.answer;
        } else {
          responseDiv.textContent = "Error: " + (data.error || "Unknown error");
          responseDiv.style.color = "red";
        }
      } catch (err) {
        responseDiv.textContent = "Network error - please try again";
        responseDiv.style.color = "red";
      }
    }

    // Allow pressing Enter to submit
    document.getElementById("question").addEventListener("keypress", function(e) {
      if (e.key === "Enter") ask();
    });
  </script>
</body>
</html>
    """


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)