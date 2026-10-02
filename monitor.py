import os
from collections import deque
import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
MONITOR_USER_ID = int(os.getenv("MONITOR_USER_ID", "0"))
MONITOR_CHANNEL_IDS = {
    int(x.strip()) for x in os.getenv("MONITOR_CHANNEL_IDS", "").split(",")
    if x.strip().isdigit()
}

events = deque(maxlen=50)

class MonitorBot(discord.Client):
    async def setup_hook(self):
        await tree.sync()

intents = discord.Intents.default()
intents.guilds = True
intents.messages = True

bot = MonitorBot(intents=intents)
tree = app_commands.CommandTree(bot)

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if MONITOR_USER_ID and message.author.id != MONITOR_USER_ID:
        return
    if MONITOR_CHANNEL_IDS and message.channel.id not in MONITOR_CHANNEL_IDS:
        return

    now = discord.utils.utcnow()
    created = message.created_at
    gateway_ms = max(0.0, (now - created).total_seconds() * 1000.0)

    gap_ms = None
    if events:
        gap_ms = (created - events[-1]["created"]).total_seconds() * 1000.0

    events.append({
        "created": created,
        "channel_id": message.channel.id,
        "message_id": message.id,
        "gateway_ms": gateway_ms,
        "gap_ms": gap_ms,
    })

    gap_text = "FIRST" if gap_ms is None else f"GAP={gap_ms:.0f}ms"
    print(
        f"ACCEPTED channel={message.channel.id} "
        f"time={created.isoformat()} {gap_text} "
        f"gateway~{gateway_ms:.0f}ms message_id={message.id}"
    )

@tree.command(name="monitorstatus", description="Show recent observed messages")
async def monitorstatus(interaction: discord.Interaction):
    if not events:
        await interaction.response.send_message("No messages observed yet.", ephemeral=True)
        return

    lines = ["Recent observed messages:"]
    for e in list(events)[-5:]:
        gap = "first" if e["gap_ms"] is None else f"{e['gap_ms']:.0f} ms gap"
        lines.append(
            f"<#{e['channel_id']}> — {e['created'].strftime('%H:%M:%S.%f')[:-3]} UTC "
            f"— {gap} — gateway ~{e['gateway_ms']:.0f} ms"
        )
    await interaction.response.send_message("\n".join(lines), ephemeral=True)

@bot.event
async def on_ready():
    print(f"MONITOR ONLINE: {bot.user}")

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is missing.")

bot.run(TOKEN)
