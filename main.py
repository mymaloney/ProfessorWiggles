import os
import discord
import aiohttp
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from bs4 import BeautifulSoup
import re

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


async def send_poem(target_channel=None):
    if target_channel is None:
        target_channel = bot.get_channel(POEM_CHANNEL_ID)
    if not target_channel:
        print("Poem channel not found.")
        return

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://www.poetryfoundation.org/poems/poem-of-the-day") as resp:
                html = await resp.text()
                soup = BeautifulSoup(html, 'html.parser')

                poem_link_tag = soup.select_one('a[href^="/poetrymagazine/poems/"]')
                if not poem_link_tag:
                    await target_channel.send("Could not find the poem link.")
                    return
                poem_url = "https://www.poetryfoundation.org" + poem_link_tag['href']

            async with session.get(poem_url) as poem_resp:
                poem_html = await poem_resp.text()
                poem_soup = BeautifulSoup(poem_html, 'html.parser')

                title_tag = poem_soup.select_one('h4.type-gamma')
                title = title_tag.text.strip() if title_tag else "Untitled"

                author_tag = poem_soup.select_one('div.type-kappa')
                author_spans = author_tag.find_all('span') if author_tag else []
                author = author_spans[-1].text.strip() if author_spans else (
                    author_tag.text.strip() if author_tag else "Unknown")

                poem_div = poem_soup.select_one('div.rich-text')
                if not poem_div:
                    await target_channel.send("Could not extract the poem text.")
                    return

                for br in poem_div.find_all('br'):
                    br.replace_with('')

                poem_text = poem_div.get_text(separator="\n").strip()
                poem_text = re.sub(r'\n{3,}', '\n\n', poem_text)

            intro = f"**{title}** by *{author}*\n<{poem_url}>"
            await target_channel.send(intro)

            chunks = [poem_text[i:i + 1900] for i in range(0, len(poem_text), 1900)]
            for chunk in chunks:
                await target_channel.send(chunk)

    except Exception as e:
        print(f"Error fetching poem: {e}")
        await target_channel.send("An error occurred while fetching the poem.")


@bot.command()
async def dog(ctx):
    await send_dog()


@bot.command()
async def poem(ctx):
    await send_poem(ctx.channel)


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    print("🔁 Scheduler starting...")

    eastern = ZoneInfo("America/New_York")

    scheduler.add_job(send_dog, CronTrigger(hour=6, minute=0, timezone=eastern))
    scheduler.add_job(send_poem, CronTrigger(hour=6, minute=5, timezone=eastern))

    async def test_message():
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            await channel.send("@maloneyman Please don't fire me, I'm working now.")

    scheduler.add_job(test_message, CronTrigger(hour=14, minute=50, timezone=eastern))
    scheduler.start()

    print("✅ Scheduler started.")


bot.run(TOKEN)

