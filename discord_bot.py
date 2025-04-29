import os, requests, discord, dotenv, asyncio
dotenv.load_dotenv()
FLASK_URL = os.getenv("FLASK_URL", "http://localhost:8080/chat")
TOKEN     = os.getenv("DISCORD_TOKEN")

class SportsAssistant(discord.Client):
    async def on_ready(self):
        print(f"🤖 logged in as {self.user}")

    async def on_message(self, msg):
        if msg.author.bot or not msg.content.startswith("!ask"):
            return
        q = msg.content.removeprefix("!ask ").strip()
        try:
            r = requests.post(FLASK_URL, json={"question": q}, timeout=10)
            ans = r.json().get("answer", "No answer.")
            await msg.channel.send(ans)
        except Exception as e:
            await msg.channel.send(f"Error: {e}")

intents = discord.Intents.default()
SportsAssistant(intents=intents).run(TOKEN)
