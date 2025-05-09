"""
Discord bot for NBA Q & A
────────────────────────────────────────────────────────────────────
Runs in Cloud Run:
• A tiny HTTP server on port 8080 keeps the revision “healthy”.
• The main thread logs into Discord and proxies !ask questions
  to the Flask API defined by $FLASK_URL.
"""
# ── std-lib ──────────────────────────────────────────────────────
import os, json, threading, http.server, socketserver, asyncio
# ── third-party ──────────────────────────────────────────────────
import aiohttp
import discord
from discord.ext import commands

# ─────────────────────────────────────────────────────────────────
# 1. background health server  (required by Cloud Run)
# ─────────────────────────────────────────────────────────────────
PORT = int(os.getenv("PORT", "8080"))  # Cloud Run injects PORT=8080


def _health():
    """Respond 200 OK to any request so Cloud Run knows we’re alive."""
    handler = http.server.SimpleHTTPRequestHandler
    # Silence noisy request logs
    handler.log_message = lambda *a, **kw: None
    with socketserver.TCPServer(("", PORT), handler) as httpd:
        httpd.serve_forever()


threading.Thread(target=_health, daemon=True).start()

# ─────────────────────────────────────────────────────────────────
# 2. Discord client setup
# ─────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents, case_insensitive=True)

API_URL = os.getenv("FLASK_URL", "").rstrip("/")        # set as secret
TOKEN   = os.getenv("DISCORD_TOKEN")                    # set as secret

# ─────────────────────────────────────────────────────────────────
# 3. Events & commands
# ─────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    print(f"✅  Logged in as {bot.user} ({bot.user.id})")


@bot.command()
async def hello(ctx):
    """Connection test."""
    await ctx.send(f"Hello {ctx.author.name}! 👋")


@bot.command(aliases=["ask"])
async def stats(ctx, *, question: str):
    """Send any free-form question to the Flask API and echo the answer."""
    if not API_URL:
        await ctx.send("⚠️  API URL not configured.")
        return

    payload = {"question": question}
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(f"{API_URL}/chat", json=payload) as resp:
                if resp.status == 200:
                    data   = await resp.json()
                    answer = data.get("answer") or data
                    await ctx.send(str(answer)[:1800])   # Discord message limit
                else:
                    await ctx.send(f"API error {resp.status}")
    except Exception as exc:
        await ctx.send(f"Request failed: {exc}")


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❓  Unknown command – try `!hello`.")
    else:
        await ctx.send(f"Error: {error}")


# ─────────────────────────────────────────────────────────────────
# 4. Entry point
# ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN environment variable is missing!")
    bot.run(TOKEN)
