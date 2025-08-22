import os
import asyncio
import logging
from datetime import datetime, date
from zoneinfo import ZoneInfo

import discord
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# ── Config ───────────────────────────────────────────────────────────────
PACIFIC_TZ = ZoneInfo("America/Los_Angeles")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")                   # required (never hardcode)
TARGET_CHANNEL_ID = int(os.getenv("TARGET_CHANNEL_ID", "0")) # required
COMMAND_PREFIX = os.getenv("COMMAND_PREFIX", "!")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
intents = discord.Intents.default()
bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)
scheduler = AsyncIOScheduler(timezone=PACIFIC_TZ)

# ── Calculator (replicates 7catyear logic we derived) ────────────────────
MASTER_SET = {11, 22, 33}

def digit_sum(n: int) -> int:
    return sum(int(c) for c in str(abs(n)))

def reduce_number(n: int) -> int:
    """
    Reduce to a single digit unless a master number (11, 22, 33) appears during reduction.
    """
    s = digit_sum(n)
    if s in MASTER_SET:
        return s
    while s > 9:
        s = digit_sum(s)
        if s in MASTER_SET:
            return s
    return s

def life_path_for_date(d: date) -> dict:
    """
    Returns:
      - life_path_primary: master-aware reduction of (year + month + day)
      - digits_total: sum of all digits in YYYYMMDD (raw total, not master logic)
      - secondary_energy: reduced day (master-aware)
    """
    y, m, dd = d.year, d.month, d.day

    full_sum = y + m + dd                # e.g., 2025 + 8 + 21 = 2054
    life_path_primary = reduce_number(full_sum)  # → master-aware (e.g., 11)

    digits_total = digit_sum(int(f"{y:04d}{m:02d}{dd:02d}"))  # e.g., 0+8+2+1+2+0+2+5 = 20

    secondary_energy = reduce_number(dd) # e.g., 21 → 3

    return {
        "life_path_primary": life_path_primary,
        "digits_total": digits_total,
        "secondary_energy": secondary_energy,
    }

def build_url_for_date(d: date) -> str:
    return f"https://7catyear.com/?birthdate={d.strftime('%m/%d/%Y')}"

async def post_for_date(d: date, channel: discord.abc.Messageable):
    calc = life_path_for_date(d)
    url = build_url_for_date(d)
    title = f"Daily 7CatYear — {d.strftime('%B %d, %Y')} (PT)"
    msg = (
        f"**{title}**\n"
        f"URL: {url}\n"
        f"Life Path: **{calc['life_path_primary']} / {calc['digits_total']}**\n"
        f"Secondary energy: **{calc['secondary_energy']}**"
    )
    await channel.send(msg)

async def post_for_today():
    today_pt = datetime.now(PACIFIC_TZ).date()
    channel = bot.get_channel(TARGET_CHANNEL_ID)
    if not channel:
        logging.error("Channel %s not found. Set TARGET_CHANNEL_ID correctly.", TARGET_CHANNEL_ID)
        return
    await post_for_date(today_pt, channel)

# ── Commands ─────────────────────────────────────────────────────────────
@bot.command(name="today")
async def cmd_today(ctx: commands.Context):
    """Post today's numbers immediately."""
    await ctx.trigger_typing()
    await post_for_today()
    await ctx.send("Posted today's Life Path above ☝️")

@bot.command(name="calc")
async def cmd_calc(ctx: commands.Context, mmddyyyy: str):
    """
    Compute for any date.
    Usage: !calc 08/21/2025
    """
    try:
        d = datetime.strptime(mmddyyyy, "%m/%d/%Y").date()
    except ValueError:
        await ctx.send("Use MM/DD/YYYY, e.g. `!calc 08/21/2025`")
        return
    await ctx.trigger_typing()
    await post_for_date(d, ctx.channel)

# ── Lifecycle ────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    logging.info("Logged in as %s (ID: %s)", bot.user, bot.user.id)
    # Run daily at 08:00 Pacific (PST/PDT handled by tz database)
    scheduler.add_job(lambda: asyncio.create_task(post_for_today()),
                      CronTrigger(hour=8, minute=0))
    scheduler.start()

if __name__ == "__main__":
    if not DISCORD_TOKEN or TARGET_CHANNEL_ID == 0:
        raise SystemExit("Set DISCORD_TOKEN and TARGET_CHANNEL_ID environment variables.")
    bot.run(DISCORD_TOKEN)
