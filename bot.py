import asyncio
import json
import os
import xml.etree.ElementTree as ET
from collections import deque
from pathlib import Path

import discord
import feedparser
from discord import app_commands
from discord.ext import tasks
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
CHANNEL_ID_RAW = os.getenv("CHANNEL_ID", "0").strip()
if not CHANNEL_ID_RAW.isdigit():
    raise RuntimeError("CHANNEL_ID must contain only the numeric Discord channel ID.")
CHANNEL_ID = int(CHANNEL_ID_RAW)
OPML_FILE = os.getenv("OPML_FILE", "feedly.opml")

SEEN_FILE = Path("seen_links.json")
seen_links = set()

monitor_events = deque(maxlen=50)
monitor_user_id = 0
monitor_channel_ids = set()


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

            published = entry.get("published_parsed") or entry.get("updated_parsed")

            articles.append(
                {
                    "title": title,
                    "link": link,
                    "source": source,
                    "published": published,
                }
            )

    unique = {}
    for article in articles:
        unique[article["link"]] = article

    articles = list(unique.values())

    articles.sort(
        key=lambda article: article["published"] or (0, 0, 0, 0, 0, 0, 0, 0, 0),
        reverse=True,
    )

    return articles


class NewsBot(discord.Client):
    async def setup_hook(self):
        await tree.sync()


intents = discord.Intents.default()
intents.guilds = True
intents.messages = True

bot = NewsBot(intents=intents)
tree = app_commands.CommandTree(bot)


@tree.command(name="news", description="Get one latest RSS news article")
async def news(interaction: discord.Interaction):
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

    article = articles[0]

    await interaction.followup.send(
        f"📰 **{article['title']}**\n"
        f"Source: {article['source']}\n"
        f"{article['link']}"
    )


@tree.command(
    name="monitor",
    description="Monitor your messages in one text channel",
)
@app_commands.describe(channel="Channel to monitor. Leave blank to use this channel.")
async def monitor(
    interaction: discord.Interaction,
    channel: discord.TextChannel | None = None,
):
    global monitor_user_id, monitor_channel_ids

    target = channel or interaction.channel
    if not isinstance(target, discord.TextChannel):
        await interaction.response.send_message(
            "Use this command inside a server text channel or choose a text channel.",
            ephemeral=True,
        )
        return

    monitor_user_id = interaction.user.id
    monitor_channel_ids = {target.id}
    monitor_events.clear()

    await interaction.response.send_message(
        f"Monitoring your messages in {target.mention}.",
        ephemeral=True,
    )


@tree.command(
    name="monitoradd",
    description="Add another text channel to the monitor",
)
@app_commands.describe(channel="Channel to add. Leave blank to use this channel.")
async def monitoradd(
    interaction: discord.Interaction,
    channel: discord.TextChannel | None = None,
):
    global monitor_user_id

    target = channel or interaction.channel
    if not isinstance(target, discord.TextChannel):
        await interaction.response.send_message(
            "Use this command inside a server text channel or choose a text channel.",
            ephemeral=True,
        )
        return

    monitor_user_id = interaction.user.id
    monitor_channel_ids.add(target.id)

    await interaction.response.send_message(
        f"Added {target.mention}. Now monitoring {len(monitor_channel_ids)} channel(s).",
        ephemeral=True,
    )


@tree.command(
    name="monitoroff",
    description="Stop monitoring messages",
)
async def monitoroff(interaction: discord.Interaction):
    global monitor_user_id

    monitor_channel_ids.clear()
    monitor_events.clear()
    monitor_user_id = 0

    await interaction.response.send_message(
        "Message monitoring stopped.",
        ephemeral=True,
    )


@tree.command(
    name="monitorstatus",
    description="Show monitor channels and recent observed messages",
)
async def monitorstatus(interaction: discord.Interaction):
    if not monitor_channel_ids:
        await interaction.response.send_message(
            "Monitor is off. Use /monitor to start it.",
            ephemeral=True,
        )
        return

    lines = [
        "Monitoring: " + ", ".join(f"<#{cid}>" for cid in sorted(monitor_channel_ids))
    ]

    if not monitor_events:
        lines.append("No monitored messages observed yet.")
    else:
        lines.append("Recent observed messages:")
        for event in list(monitor_events)[-5:]:
            gap = (
                "first"
                if event["gap_ms"] is None
                else f"{event['gap_ms']:.0f} ms gap"
            )
            lines.append(
                f"<#{event['channel_id']}> — "
                f"{event['created_at'].strftime('%H:%M:%S.%f')[:-3]} UTC — "
                f"{gap} — gateway ~{event['gateway_ms']:.0f} ms"
            )

    await interaction.response.send_message(
        "\n".join(lines),
        ephemeral=True,
    )


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return

    if monitor_user_id == 0 or message.author.id != monitor_user_id:
        return

    if message.channel.id not in monitor_channel_ids:
        return

    observed_at = discord.utils.utcnow()
    created_at = message.created_at
    gateway_ms = max(
        0.0,
        (observed_at - created_at).total_seconds() * 1000.0,
    )

    gap_ms = None
    if monitor_events:
        gap_ms = (
            created_at - monitor_events[-1]["created_at"]
        ).total_seconds() * 1000.0

    monitor_events.append(
        {
            "created_at": created_at,
            "channel_id": message.channel.id,
            "message_id": message.id,
            "gateway_ms": gateway_ms,
            "gap_ms": gap_ms,
        }
    )

    gap_text = "FIRST" if gap_ms is None else f"GAP={gap_ms:.0f}ms"
    channel_name = getattr(message.channel, "name", str(message.channel.id))

    print(
        f"[ACCEPTED] #{channel_name} "
        f"time={created_at.isoformat()} "
        f"{gap_text} "
        f"gateway~{gateway_ms:.0f}ms "
        f"message_id={message.id}"
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

    if not new_articles:
        print("No new articles found.")
        return

    article = new_articles[0]

    await channel.send(
        f"📰 **{article['title']}**\n"
        f"Source: {article['source']}\n"
        f"{article['link']}"
    )

    seen_links.add(article["link"])
    save_seen_links(seen_links)


@news_loop.before_loop
async def before_news_loop():
    await bot.wait_until_ready()
    await asyncio.sleep(1800)


@bot.event
async def on_ready():
    print(f"NEWS + MONITOR BOT ONLINE: {bot.user}")

    if not news_loop.is_running():
        news_loop.start()


if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is missing. Create a .env file and add your token."
    )

bot.run(TOKEN)
