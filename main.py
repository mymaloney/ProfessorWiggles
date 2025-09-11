import os
import discord
import aiohttp
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import asyncio
import random
from zoneinfo import ZoneInfo
from flask import Flask
import threading

TOKEN = os.environ["TOKEN"]
CHANNEL_ID = 1362377128556888164  # replace with your channel ID
DOG_CHANNEL = 1362449863513473339
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

scheduler = AsyncIOScheduler()

# --- Flask keep-alive ---
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running."

def run_web():
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))

# Run Flask in a separate thread
threading.Thread(target=run_web).start()

# --- Dog Command ---
@bot.command()
async def dog(ctx):
    channel = ctx.channel
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://dog.ceo/api/breeds/image/random") as resp:
                data = await resp.json()
                await channel.send(data["message"])
    except Exception as e:
        await channel.send(f"Failed to fetch dog image: {e}")

# --- Cat Command ---
@bot.command()
async def cat(ctx):
    url = "https://api.thecatapi.com/v1/images/search"
    headers = {"x-api-key": "live_IVLwPo7y4QmgTfaX4LbCUEkfVhKxJHjgV6IE0PhHPp2oYx4hqRC1qSb9q4nz6NAI"}  # Optional
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                data = await resp.json()
                cat_url = data[0]["url"]
                await ctx.send(cat_url)
    except Exception as e:
        await ctx.send(f"Failed to fetch cat image: {e}")

# --- Grade Command ---
@bot.command()
async def grade(ctx):
    if not ctx.message.attachments:
        await ctx.send("Awooo? You didn't submit anything!")
        return

    grading_msg = await ctx.send("Grading...")
    wait_time = random.randint(1, 360)
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
        "Wow. Truly inspired mediocrity. D.",
        "I mean… you tried. A for effort. But C.",
        "It made me laugh.... I mean, really, laugh... A plus.",
        "Hate has no place here, youngster. F minus.",
        "Creative? Yes. Good? Debatable. C-.",
        "It's giving.... A plus.",
        "This made me smile! :) A.",
        "Remarkable effort! Keep it up. B plus.",
        "I can tell you care, and it shows. A.",
        "Innoffensive. D."
    ]

    response = random.choice(grades)
    await grading_msg.edit(content=response)

# --- Scheduled Ping ---
async def ping_for_poem():
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        await channel.send("@maloneyman Time for the daily poem!")
        print("✅ Sent daily ping for poem.")

async def daily_dog():
    channel = bot.get_channel(DOG_CHANNEL)
    if channel:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get("https://dog.ceo/api/breeds/image/random") as resp:
                    data = await resp.json()
                    await channel.send(data["message"])
        except Exception as e:
            await channel.send(f"Failed to fetch dog image: {e}")

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    eastern = ZoneInfo("America/New_York")

    # Schedule daily ping at 6 AM
    scheduler.add_job(ping_for_poem, CronTrigger(hour=6, minute=0, timezone=eastern))
    scheduler.add_job(daily_dog, CronTrigger(hour=6, minute=0, timezone=eastern))
    scheduler.start()
    print("✅ Scheduler started.")

bot.run(TOKEN)
