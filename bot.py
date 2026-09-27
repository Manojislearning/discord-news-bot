import json
import os
import random
import xml.etree.ElementTree as ET
from pathlib import Path

import discord
import feedparser
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "0"))
OPML_FILE = os.getenv("OPML_FILE", "feedly.opml")

SEEN_FILE = Path("seen_links.json")
MAX_AUTO_POSTS = 10


def load_seen_links():
    if not SEEN_FILE.exists():
        return set()
    try:
        return set(json.loads(SEEN_FILE.read_text(encoding="utf-8")))
    except Exception:
        return set()


def save_seen_links(links):
    SEEN_FILE.write_text(
        json.dumps(sorted(links), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


seen_links = load_seen_links()


def get_feed_urls():
    tree = ET.parse(OPML_FILE)
    root = tree.getroot()

    urls = []
    for outline in root.findall(".//outline"):
        url = outline.attrib.get("xmlUrl")
        if url:
            urls.append(url)

    return list(dict.fromkeys(urls))


def get_all_articles():
    articles = []

    for url in get_feed_urls():
        feed = feedparser.parse(url)
        source = feed.feed.get("title", "Unknown source")

        for entry in feed.entries[:10]:
            link = entry.get("link", "")
            title = entry.get("title", "Untitled")

            if not link:
                continue

            articles.append(
                {
                    "title": title,
                    "link": link,
                    "source": source,
                }
            )

    # Remove duplicates by link.
    unique = {}
    for article in articles:
        unique[article["link"]] = article

    return list(unique.values())


class NewsBot(discord.Client):
    async def setup_hook(self):
        await tree.sync()


intents = discord.Intents.default()
bot = NewsBot(intents=intents)
tree = app_commands.CommandTree(bot)


@tree.command(name="randomnews", description="Get one random article from the RSS feeds")
async def randomnews(interaction: discord.Interaction):
    await interaction.response.defer()

    try:
        articles = get_all_articles()
    except FileNotFoundError:
        await interaction.followup.send(
            f"Could not find {OPML_FILE}. Put your Feedly OPML export beside bot.py."
        )
        return
    except Exception as exc:
        await interaction.followup.send(f"Could not read RSS feeds: {exc}")
        return

    if not articles:
        await interaction.followup.send("No articles found.")
        return

    article = random.choice(articles)

    await interaction.followup.send(
        f"📰 **{article['title']}**\n"
        f"Source: {article['source']}\n"
        f"{article['link']}"
    )


@tree.command(name="news", description="Get the latest available RSS articles")
async def news(interaction: discord.Interaction):
    await interaction.response.defer()

    try:
        articles = get_all_articles()[:10]
    except FileNotFoundError:
        await interaction.followup.send(
            f"Could not find {OPML_FILE}. Put your Feedly OPML export beside bot.py."
        )
        return
    except Exception as exc:
        await interaction.followup.send(f"Could not read RSS feeds: {exc}")
        return

    if not articles:
        await interaction.followup.send("No articles found.")
        return

    for article in articles:
        await interaction.followup.send(
            f"📰 **{article['title']}**\n"
            f"Source: {article['source']}\n"
            f"{article['link']}"
        )


@tasks.loop(minutes=30)
async def news_loop():
    if CHANNEL_ID == 0:
        print("CHANNEL_ID is not set.")
        return

    channel = bot.get_channel(CHANNEL_ID)
    if channel is None:
        print("Channel not found. Check CHANNEL_ID and bot permissions.")
        return

    try:
        articles = get_all_articles()
    except FileNotFoundError:
        print(f"Could not find {OPML_FILE}.")
        return
    except Exception as exc:
        print(f"RSS error: {exc}")
        return

    new_articles = [a for a in articles if a["link"] not in seen_links]
    new_articles = new_articles[:MAX_AUTO_POSTS]

    for article in new_articles:
        await channel.send(
            f"📰 **{article['title']}**\n"
            f"Source: {article['source']}\n"
            f"{article['link']}"
        )
        seen_links.add(article["link"])

    if new_articles:
        save_seen_links(seen_links)


@news_loop.before_loop
async def before_news_loop():
    await bot.wait_until_ready()


@bot.event
async def on_ready():
    print(f"NEWS BOT ONLINE: {bot.user}")

    if not news_loop.is_running():
        news_loop.start()


if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is missing. Create a .env file from .env.example and add your token."
    )

bot.run(TOKEN)
