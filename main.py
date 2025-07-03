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

def html_to_discord_markdown(soup):
    # Italic: <i> or <em> -> *text*
    for tag in soup.find_all(['i', 'em']):
        tag.insert_before('*')
        tag.insert_after('*')
        tag.unwrap()

    # Bold: <b> or <strong> -> **text**
    for tag in soup.find_all(['b', 'strong']):
        tag.insert_before('**')
        tag.insert_after('**')
        tag.unwrap()

    # Underline: <u> -> __text__
    for tag in soup.find_all('u'):
        tag.insert_before('__')
        tag.insert_after('__')
        tag.unwrap()

    # Strikethrough: <s> or <del> -> ~~text~~
    for tag in soup.find_all(['s', 'del']):
        tag.insert_before('~~')
        tag.insert_after('~~')
        tag.unwrap()

    return soup

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

async def send_poem(target_channel=None):
    if target_channel is None:
        target_channel = bot.get_channel(POEM_CHANNEL_ID)
    if not target_channel:
        print("Poem channel not found.")
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://www.poetryfoundation.org/poems/poem-of-the-day", allow_redirects=True) as resp:
                poem_url = str(resp.url)

            async with session.get(poem_url) as poem_resp:
                poem_html = await poem_resp.text()
                poem_soup = BeautifulSoup(poem_html, 'html.parser')

                title_tag = poem_soup.select_one('h4.type-gamma')
                title = title_tag.text.strip() if title_tag else "Untitled"

                author_tag = poem_soup.select_one('div.type-kappa')
                author_spans = author_tag.find_all('span') if author_tag else []
                author = author_spans[-1].text.strip() if author_spans else (
                    author_tag.text.strip() if author_tag else "Unknown")

                poem_div = poem_soup.select_one('div.rich-text.col-span-full')
                if not poem_div:
                    await target_channel.send("Could not extract the poem text.")
                    return

                # === Fixed <br> handling ===
                br_tags = poem_div.find_all('br')
                i = 0
                while i < len(br_tags):
                    current_br = br_tags[i]
                    consecutive = [current_br]
                    j = i + 1
                    # Collect consecutive sibling <br> tags
                    while j < len(br_tags) and br_tags[j].previous_sibling == br_tags[j-1]:
                        consecutive.append(br_tags[j])
                        j += 1
                    # Remove all but first <br>
                    for br_to_remove in consecutive[1:]:
                        br_to_remove.decompose()
                    # Replace the first <br> with a newline text node
                    consecutive[0].replace_with('\n')
                    i = j

                # Replace non-breaking spaces (&nbsp;) with regular spaces
                for elem in poem_div.find_all(text=True):
                    elem.replace_with(elem.replace('\xa0', ' '))

                poem_text = poem_div.get_text().strip()

            intro = f"**{title}** by *{author}*\n<{poem_url}>"
            await target_channel.send(intro)

            # Send poem in chunks if too long
            chunks = [poem_text[i:i + 1900] for i in range(0, len(poem_text), 1900)]
            for chunk in chunks:
                await target_channel.send(chunk)

    except Exception as e:
        print(f"Error fetching poem: {e}")
        await target_channel.send("An error occurred while fetching the poem.")

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
