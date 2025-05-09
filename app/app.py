import os, re, sqlite3, requests, logging, json
from flask import Flask, request, jsonify
import dotenv

dotenv.load_dotenv()
API_KEY = os.getenv("TSD_KEY", "3")  # TheSportsDB API key (default "3" for demo)
DB_PATH = os.path.join(os.path.dirname(__file__), "nba_stats.db")
BASE_URL = f"https://www.thesportsdb.com/api/v1/json/{API_KEY}"

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)  # Configure logging for debugging

# Team name normalization for common aliases/typos
TEAM_ALIASES = {
    'wantnos': 'washington wizards',
    'wiz': 'washington wizards',
    'lakers': 'los angeles lakers',
    'celtics': 'boston celtics',
    'celllics': 'boston celtics',  # handle common misspelling
    'warriors': 'golden state warriors',
    'heat': 'miami heat',
    # ... add more aliases as needed ...
}

def normalize_team_name(team_name: str) -> str:
    """Normalize team names and handle common aliases/typos."""
    return TEAM_ALIASES.get(team_name.lower().strip(), team_name.lower().strip())

def query_local(team: str, season: int):
    """Query the local SQLite database for a team's stats in a given season."""
    query = (
        "SELECT pts, fgm, fga, \"fg%\", ast, trb "
        "FROM team_stats "
        "WHERE team LIKE ? AND season = ?"
    )
    try:
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(query, (f"%{team}%", season)).fetchone()
    except sqlite3.Error as e:
        logging.error(f"Database error querying local stats: {e}")
        return None
    if row:
        # Map query result to dict with readable keys
        return dict(zip(["PTS", "FGM", "FGA", "FG%", "AST", "REB"], row))
    return None

def query_tsdb(endpoint: str, **params):
    """Query TheSportsDB API for the given endpoint and parameters."""
    url = f"{BASE_URL}/{endpoint}.php"
    logging.info(f"Calling external API: {url} params={params}")
    r = requests.get(url, params=params, timeout=10)
    r.raise_for_status()
    return r.json()

def extract_team_name(question: str, trigger_phrase: str) -> str:
    """Extract and normalize team name from the question text following a trigger phrase."""
    # Take the part of the question after the trigger phrase
    part = question.split(trigger_phrase, 1)[-1]
    # Keep only alphabetic words (strip punctuation/numbers)
    team_name = " ".join(word for word in part.split() if word.isalpha()).strip()
    return normalize_team_name(team_name)

@app.post("/chat")
def chat():
    # Parse the JSON request
    data = request.get_json(silent=True)
    if not data or 'question' not in data:
        return jsonify(error="Invalid request format: JSON with 'question' field required."), 400

    question = data.get("question", "").lower()
    logging.info(f"Received question: {question}")
    try:
        # 1. Handle queries about average points (PPG) for a team in a season
        if "average" in question and ("points" in question or "ppg" in question):
            # Find a 4-digit year in the question (default to 2023 if not found)
            match = re.search(r"(\d{4})", question)
            season = int(match.group(1)) if match else 2023
            team = extract_team_name(question, "average" if "average" in question else "ppg")

            if len(team) < 3:  # too short to be a valid team name
                return jsonify(answer="Please provide a full team name."), 200

            stats = query_local(team, season)
            if stats:
                answer_text = (
                    f"In {season}, {team.title()} averaged:\n"
                    f"• Points: {stats['PTS']} PPG\n"
                    f"• Field Goal %: {stats['FG%']}\n"
                    f"• Assists: {stats['AST']}\n"
                    f"• Rebounds: {stats['REB']}"
                )
                return jsonify(answer=answer_text), 200
            else:
                return jsonify(answer=f"Sorry, no stats available for {team.title()} in {season}."), 200

        # 2. Handle queries about the last game/result for a team
        if any(phrase in question for phrase in ["last game", "recent result", "last match"]):
            # Determine which trigger phrase was used
            if "last game" in question:
                trigger = "last game"
            elif "recent result" in question:
                trigger = "recent result"
            else:
                trigger = "last match"
            team_name = extract_team_name(question, trigger)

            if len(team_name) < 3:
                return jsonify(answer="Please provide a full team name."), 200

            # Search team by name via TheSportsDB API
            search_data = query_tsdb("searchteams", t=team_name)
            teams_list = search_data.get("teams")
            if not teams_list:
                return jsonify(answer=f"Team '{team_name.title()}' not found. Try using an official team name or city."), 200

            # Find the specific NBA team in search results (TheSportsDB may return multiple sports)
            nba_team = next((team for team in teams_list if team.get("strLeague") == "NBA"), None)
            if not nba_team:
                return jsonify(answer=f"'{team_name.title()}' does not appear to be an NBA team."), 200

            # Get the last event (game) for that team
            team_id = nba_team["idTeam"]
            events_data = query_tsdb("eventslast", id=team_id)
            if not events_data.get("results"):
                return jsonify(answer=f"No recent games found for {nba_team['strTeam']}."), 200

            last_game = events_data["results"][0]
            home_team = last_game.get('strHomeTeam', 'Unknown')
            away_team = last_game.get('strAwayTeam', 'Unknown')
            home_score = last_game.get('intHomeScore', '?')
            away_score = last_game.get('intAwayScore', '?')
            date = last_game.get('dateEvent', 'unknown date')
            answer_text = (
                f"🏀 {nba_team['strTeam']}'s Last Game:\n"
                f"• Matchup: {home_team} vs {away_team}\n"
                f"• Score: {home_score}-{away_score}\n"
                f"• Date: {date}"
            )
            return jsonify(answer=answer_text), 200

        # 3. Fallback response for any other queries
        return jsonify(answer=(
            "I can help with:\n"
            "• Team averages: 'What did the Lakers average in 2020?'\n"
            "• Recent games: 'Last game for the Warriors'\n\n"
            "Please try one of these questions."
        )), 200

    except requests.RequestException as e:
        logging.error(f"External API request failed: {e}")
        return jsonify(error="Failed to retrieve data from external API."), 502
    except Exception as e:
        logging.exception(f"Unexpected error: {e}")
        return jsonify(error=f"Unexpected server error: {e}"), 500

@app.get("/")
def home():
    # Simple HTML page to interact with the chatbot
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
        <p>Ask about team statistics or recent games:</p>
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
          // Allow pressing Enter to submit the question
          document.getElementById("question").addEventListener("keypress", function(e) {
            if (e.key === "Enter") ask();
          });
        </script>
      </body>
    </html>
    """

if __name__ == "__main__":
    # Run the Flask development server for local testing
    app.run(host="0.0.0.0", port=8080)
