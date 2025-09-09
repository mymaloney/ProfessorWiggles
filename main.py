import os
import discord
import aiohttp
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from bs4 import BeautifulSoup
import re
from flask import Flask
import threading
import datetime
import asyncio
import random

poem_cache = {}

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running."

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# Start the keep-alive web server in a thread
threading.Thread(target=run_web).start()

# Use zoneinfo for Python 3.9+, else fallback to pytz
try:
    from zoneinfo import ZoneInfo
except ImportError:
    from pytz import timezone as ZoneInfo

# Bot setup
TOKEN = os.environ["TOKEN"]
CHANNEL_ID = 1362449863513473339
POEM_CHANNEL_ID = 1362377128556888164

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

scheduler = AsyncIOScheduler()

async def send_dog():
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://dog.ceo/api/breeds/image/random") as resp:
                    data = await resp.json()
                    await channel.send(data["message"])
        except Exception as e:
            print(f"Failed to send dog image: {e}")
# === Fresh rewrite of poem fetching + sending ===

async def fetch_poem():
    """
    Grab a poem from poems.one. Returns (intro, chunks, pretty).
    Uses caching so we only fetch once per day.
    """
    today = datetime.date.today().isoformat()
    if today in poem_cache:
        return poem_cache[today]

    api_url = "https://poems.one/api/poem/"
    poem_data = None

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as resp:
                if resp.status != 200:
                    print(f"Poem fetch failed with status {resp.status}")
                    return None, None, None

                # JSON decode
                try:
                    data = await resp.json()
                except Exception as e:
                    print(f"Failed to decode JSON: {e}")
                    return None, None, None

        # Extract poem
        poems = data.get("contents", {}).get("poems", [])
        if poems:
            poem_data = poems[0]

        if not poem_data:
            print("No poem found in API response.")
            return None, None, None

        # Fields
        title = poem_data.get("title", "Untitled")
        author = (poem_data.get("author") or "Unknown").strip()
        url_field = poem_data.get("url", "")

        # Content can be lines[] or content string
        raw_content = poem_data.get("content") or poem_data.get("lines", [])
        poem_text = "\n".join(raw_content) if isinstance(raw_content, list) else str(raw_content)

        # Pretty formatting like Node version
        max_line_len = max((len(line) for line in poem_text.splitlines()), default=10)
        separator = "-" * max_line_len

        pretty_block = (
            f'“{title}”\n'
            f"by {author}\n"
            f"{separator}\n\n"
            f"{poem_text}\n\n"
            f"({url_field})"
        )

        # Short intro + Discord-safe chunks
        intro = f"**{title}** by *{author}*"
        chunks = [poem_text[i:i + 1900] for i in range(0, len(poem_text), 1900)]

        # Cache it
        poem_cache[today] = (intro, chunks, pretty_block)
        return intro, chunks, pretty_block

    except Exception as e:
        print(f"Unexpected poem fetch error: {e}")
        return None, None, None


async def send_poem(target_channel=None):
    """
    Send the daily poem into a Discord channel.
    Falls back to error message if fetching fails.
    """
    if target_channel is None:
        target_channel = bot.get_channel(POEM_CHANNEL_ID)

    if not target_channel:
        print("Could not find poem channel.")
        return

    intro, chunks, pretty = await fetch_poem()

    if not intro:
        await target_channel.send("🚨 An error occurred while fetching the poem.")
        return

    # If everything fits, send as one pretty block
    if pretty and len(pretty) < 1900:
        await target_channel.send(f"```{pretty}```")
    else:
        await target_channel.send(intro)
        for chunk in chunks:
            await target_channel.send(chunk)
            await asyncio.sleep(1.5)


@bot.command()
async def debugpoem(ctx):
    intro, chunks, pretty = await fetch_poem()
    if not intro:
        await ctx.send("DEBUG: fetch_poem returned None")
        return

    await ctx.send(f"DEBUG intro: {intro}")
    if pretty:
        await ctx.send(f"DEBUG pretty (first 500):\n```{pretty[:500]}```")

    for i, chunk in enumerate(chunks):
        await ctx.send(f"DEBUG chunk {i+1}:\n{chunk[:500]}")

@bot.command()
async def dog(ctx):
    # Send dog image to channel where command was issued
    channel = ctx.channel
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://dog.ceo/api/breeds/image/random") as resp:
                data = await resp.json()
                await channel.send(data["message"])
    except Exception as e:
        await channel.send(f"Failed to fetch dog image: {e}")

@bot.command()
async def cat(ctx):
    url = "https://api.thecatapi.com/v1/images/search"
    headers = {"x-api-key": "live_IVLwPo7y4QmgTfaX4LbCUEkfVhKxJHjgV6IE0PhHPp2oYx4hqRC1qSb9q4nz6NAI"}  # Optional
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            data = await resp.json()
            cat_url = data[0]["url"]
            await ctx.send(cat_url)

@bot.command()
async def poem(ctx):
    await send_poem(ctx.channel)

@bot.command()
async def grade(ctx):
    if not ctx.message.attachments:
        await ctx.send("Awooo? You didn't submit anything!")
        return

    grading_msg = await ctx.send("Grading...")

    wait_time = random.randint(1, 360)  # 1 second to 6 minutes
    await asyncio.sleep(wait_time)

    grades = [
        "Uh. Okay. B.",
        "Really a little... pedestrian, don't you think? C.",
        "You could have done a little better and you know it. A reluctant B minus.",
        "Oh, fuck, no! Get this shit out of my sight! F.",
        "I mean, it's better than what I did at your age. B plus.",
        "Go check out #literature and think a bit about what you read there. C.",
        "Fine, but this is strike two. B plus.",
        "My god... it so shit I shit. No good. F.",
        "I'm calling the Dean. D. For Dean.",
        "I mean… you tried. A for effort. But C.",
        "It made me laugh.... I mean, really, laugh... A plus.",
        "Hate has no place here, youngster. F minus.",
        "It's giving.... A plus.",
        "Innoffensive. D."
    ]

    response = random.choice(grades)
    await grading_msg.edit(content=response)

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print("🔁 Scheduler starting...")

    eastern = ZoneInfo("America/New_York")

    # Schedule daily dog image to fixed channel
    scheduler.add_job(send_dog, CronTrigger(hour=6, minute=0, timezone=eastern))

    # Schedule daily poem to fixed poem channel
    scheduler.add_job(send_poem, CronTrigger(hour=6, minute=5, timezone=eastern))

    scheduler.start()

    print("✅ Scheduler started.")

bot.run(TOKEN)
