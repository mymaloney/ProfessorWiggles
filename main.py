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

async def schedule_daily_poem():
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = datetime.datetime.now()
        # Set the target time for 1:00 AM
        target = now.replace(hour=1, minute=0, second=0, microsecond=0)
        if now >= target:
            target += datetime.timedelta(days=1)
        wait_seconds = (target - now).total_seconds()
        await asyncio.sleep(wait_seconds)

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

async def cat(ctx):
    url = "https://api.thecatapi.com/v1/images/search"
    headers = {"x-api-key": "live_IVLwPo7y4QmgTfaX4LbCUEkfVhKxJHjgV6IE0PhHPp2oYx4hqRC1qSb9q4nz6NAI"}  # Optional, but good if you sign up
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as resp:
            data = await resp.json()
            cat_url = data[0]["url"]
            await ctx.send(cat_url)

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

                # === HERE: Fix <br> tags according to your rules ===
                br_tags = poem_div.find_all('br')
                i = 0
                while i < len(br_tags):
                    current_br = br_tags[i]
                    consecutive = [current_br]
                    j = i + 1
                    while j < len(br_tags) and br_tags[j].find_previous_sibling() == br_tags[j-1]:
                        consecutive.append(br_tags[j])
                        j += 1

                    if len(consecutive) >= 2:
                        # Keep only the first <br> in the consecutive block
                        for br_to_remove in consecutive[1:]:
                            br_to_remove.decompose()
                        i = j
                    else:
                        # Single <br> tag: remove it
                        current_br.decompose()
                        i += 1

                    br_tags = poem_div.find_all('br')

                # Replace remaining <br> with a newline
                for br in poem_div.find_all('br'):
                    br.replace_with('\n')

                # Replace non-breaking spaces
                for elem in poem_div.find_all(text=True):
                    elem.replace_with(elem.replace('\xa0', ' '))

                poem_text = poem_div.get_text().strip()

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

    scheduler.start()

    print("✅ Scheduler started.")


bot.run(TOKEN)
