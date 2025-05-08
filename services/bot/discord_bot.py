# services/bot/discord_bot.py
import os, threading
from flask import Flask
import discord
from discord.ext import commands

# 1) tiny HTTP server just for Cloud Run
site = Flask(__name__)

@site.route("/", methods=["GET", "HEAD"])
def health():
    return "bot alive", 200

# 2) start Discord bot in a background thread
def start_bot() -> None:
    intents = discord.Intents.default()
    intents.message_content = True

    bot = commands.Bot(command_prefix="!", intents=intents, case_insensitive=True)

    @bot.event
    async def on_ready():
        print(f"🤖  logged in as {bot.user} — ready to serve!")

    TOKEN = os.environ["DISCORD_TOKEN"]
    bot.run(TOKEN)

if __name__ == "__main__":
    threading.Thread(target=start_bot, daemon=True).start()
    site.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
