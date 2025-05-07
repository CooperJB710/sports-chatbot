#!/usr/bin/env python3
"""
Simple Discord wrapper that forwards !ask questions to the Flask service.
"""
import os
import requests
import discord
import dotenv
import asyncio

dotenv.load_dotenv()
FLASK_URL = os.getenv("FLASK_URL", "http://localhost:8080/chat")
TOKEN     = os.getenv("DISCORD_TOKEN")

class SportsAssistant(discord.Client):
    async def on_ready(self):
        print(f"🤖  Logged in as {self.user}")

    async def on_message(self, msg: discord.Message):
        if msg.author.bot or not msg.content.startswith("!ask"):
            return

        q = msg.content.removeprefix("!ask").strip()
        if not q:
            await msg.channel.send("Usage: `!ask <question>`")
            return

        try:
            r   = requests.post(FLASK_URL, json={"question": q}, timeout=10)
            ans = r.json().get("answer") or r.json().get("error") or "No answer."
            await msg.channel.send(ans)
        except Exception as e:
            await msg.channel.send(f"Error contacting bot API: {e}")

intents = discord.Intents.default()
intents.message_content = True
client = SportsAssistant(intents=intents)

if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("Set DISCORD_TOKEN in your environment or .env file")
    client.run(TOKEN)
