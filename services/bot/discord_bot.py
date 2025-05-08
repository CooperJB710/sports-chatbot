#!/usr/bin/env python3
import os, json, asyncio, requests, discord
from discord.ext import commands

TOKEN=os.getenv("DISCORD_TOKEN")
FLASK_URL=os.getenv("FLASK_URL")
if not TOKEN or not FLASK_URL:
    raise RuntimeError("Set DISCORD_TOKEN and FLASK_URL env-vars")

intents=discord.Intents.default(); intents.message_content=True
bot=commands.Bot(command_prefix="!",case_insensitive=True,intents=intents)

@bot.event
async def on_ready(): print(f"🤖 {bot.user} ready")

@bot.command()
async def ask(ctx, *, q:str=""):
    if not q.strip(): return await ctx.send("Usage: `!ask your question`")
    await ctx.trigger_typing()
    try:
        r=await asyncio.to_thread(
            lambda: requests.post(FLASK_URL,json={"question":q},timeout=15))
        data=r.json(); await ctx.send(data.get("answer")or data.get("error","No answer"))
    except (requests.RequestException,json.JSONDecodeError) as e:
        await ctx.send(f"API error: {e}")

bot.run(TOKEN)
