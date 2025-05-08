import os, threading, logging, requests, asyncio
from flask import Flask, request
import discord
from discord.ext import commands

TOKEN = os.environ["DISCORD_TOKEN"]
FLASK_URL = os.environ["FLASK_URL"]   # nba-api endpoint

###############################################################################
# ── Discord bot logic ────────────────────────────────────────────────────────
###############################################################################
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!ask ", intents=intents, case_insensitive=True)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} (latency {bot.latency*1000:.0f} ms)")

@bot.command(name="ask")
async def ask(ctx, *, question: str = ""):
    if not question.strip():
        await ctx.reply("Usage: `!ask <question>`")
        return
    try:
        r = requests.post(FLASK_URL, json={"question": question}, timeout=10)
        r.raise_for_status()
        data = r.json()
        await ctx.reply(data.get("answer", "No answer field in response."))
    except Exception as e:
        await ctx.reply(f"API error: {e}")

###############################################################################
# ── Flask health-check endpoint ─────────────────────────────────────────────
###############################################################################
app = Flask(__name__)

@app.get("/")
def ping():
    return "ok", 200

def run_flask():
    import waitress
    port = int(os.getenv("PORT", "8080"))
    waitress.serve(app, host="0.0.0.0", port=port)

###############################################################################
# ── main ─────────────────────────────────────────────────────────────────────
###############################################################################
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(bot.start(TOKEN))
