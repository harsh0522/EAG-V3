"""
GeoIntel Telegram Bot
Send any region/country name → get weather, top news, and YouTube links.
"""

import asyncio
import logging
import os
import time

import feedparser
import httpx
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

load_dotenv()

from usage_tracker import tracker

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

logging.basicConfig(
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("geointel.bot")


# ── Session log builder ────────────────────────────────────────────────────────

class BotSessionLog:
    """Collects all steps of one /region request for terminal + Telegram delivery."""

    def __init__(self, region: str, chat_id: int):
        self.region = region
        self.chat_id = chat_id
        self.start_ts = time.time()
        self.entries: list[str] = []
        self._step(f"SESSION START — region: {region}  |  chat_id: {chat_id}")

    def _step(self, msg: str):
        elapsed = round((time.time() - self.start_ts) * 1000, 1)
        line = f"[+{elapsed:>8.1f}ms]  {msg}"
        self.entries.append(line)
        logger.info(msg)

    def api_call(self, label: str, url: str, status: int, ms: float, summary: str):
        masked = url.replace(YOUTUBE_API_KEY, "***MASKED***") if YOUTUBE_API_KEY else url
        self._step(
            f"API CALL   {label}\n"
            f"           URL    : {masked}\n"
            f"           STATUS : {status}  |  TIME: {ms}ms\n"
            f"           RESULT : {summary}"
        )

    def api_error(self, label: str, url: str, error: str):
        masked = url.replace(YOUTUBE_API_KEY, "***MASKED***") if YOUTUBE_API_KEY else url
        self._step(
            f"API ERROR  {label}\n"
            f"           URL    : {masked}\n"
            f"           ERROR  : {error}"
        )

    def finish(self, success: bool):
        total = round((time.time() - self.start_ts) * 1000, 1)
        self._step(f"SESSION {'COMPLETE' if success else 'FAILED'}  |  Total time: {total}ms")

    def to_text(self) -> str:
        header = (
            f"GeoIntel Telegram Bot — Session Log\n"
            f"Region : {self.region}\n"
            f"{'=' * 60}\n"
        )
        return header + "\n".join(self.entries)


# ── Data fetchers ──────────────────────────────────────────────────────────────

async def fetch_weather(region: str, log: BotSessionLog) -> str:
    url = f"https://wttr.in/{region}?format=j1"
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            r = await client.get(url, headers={"User-Agent": "GeoIntelBot/1.0"})
        ms = round((time.time() - t0) * 1000, 1)
        d = r.json()
        cur = d["current_condition"][0]
        desc = cur["weatherDesc"][0]["value"]
        temp_c = cur["temp_C"]
        humidity = cur["humidity"]
        wind_kmph = cur["windspeedKmph"]
        nearest = d.get("nearest_area", [{}])[0]
        area = nearest.get("areaName", [{}])[0].get("value", region)
        country = nearest.get("country", [{}])[0].get("value", "")
        location_str = f"{area}, {country}" if country else area
        log.api_call("WEATHER (wttr.in)", url, r.status_code, ms,
                     f"{desc}, {temp_c}°C, humidity {humidity}%, wind {wind_kmph}km/h — near {location_str}")
        return (
            f"🌡 *Weather near {location_str}*\n"
            f"{desc}  •  {temp_c}°C / {cur['temp_F']}°F\n"
            f"Feels like: {cur['FeelsLikeC']}°C  •  Humidity: {humidity}%\n"
            f"Wind: {wind_kmph} km/h"
        )
    except Exception as e:
        ms = round((time.time() - t0) * 1000, 1)
        log.api_error("WEATHER (wttr.in)", url, str(e))
        return f"🌡 Weather unavailable for _{region}_"


async def fetch_news(region: str, log: BotSessionLog) -> list[tuple[str, str]]:
    url = f"https://news.google.com/rss/search?q={region}&hl=en-US&gl=US&ceid=US:en"
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            r = await client.get(url)
        ms = round((time.time() - t0) * 1000, 1)
        feed = feedparser.parse(r.text)
        articles = [(e.title, e.link) for e in feed.entries[:3]]
        log.api_call("NEWS (Google RSS)", url, r.status_code, ms,
                     f"{len(articles)} headlines fetched"
                     + (f' — top: "{articles[0][0][:60]}…"' if articles else ""))
        return articles
    except Exception as e:
        ms = round((time.time() - t0) * 1000, 1)
        log.api_error("NEWS (Google RSS)", url, str(e))
        return []


async def fetch_youtube(region: str, log: BotSessionLog) -> list[tuple[str, str]]:
    if not YOUTUBE_API_KEY or YOUTUBE_API_KEY == "YOUR_YOUTUBE_API_KEY_HERE":
        log._step("YOUTUBE    Skipped — YOUTUBE_API_KEY not configured")
        return []
    url = (
        "https://www.googleapis.com/youtube/v3/search"
        f"?part=snippet&q={region}+geopolitics&maxResults=3&type=video&key={YOUTUBE_API_KEY}"
    )
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url)
        ms = round((time.time() - t0) * 1000, 1)
        items = r.json().get("items", [])
        videos = [
            (item["snippet"]["title"], f"https://youtu.be/{item['id']['videoId']}")
            for item in items
        ]
        log.api_call("YOUTUBE (Data API v3)", url, r.status_code, ms,
                     f"{len(videos)} videos fetched"
                     + (f' — top: "{videos[0][0][:60]}…"' if videos else ""))
        tracker.record_youtube_search()
        return videos
    except Exception as e:
        ms = round((time.time() - t0) * 1000, 1)
        log.api_error("YOUTUBE (Data API v3)", url, str(e))
        return []


# ── Message builder ────────────────────────────────────────────────────────────

def escape_md(text: str) -> str:
    for ch in r"\_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text


async def build_reply(region: str, log: BotSessionLog) -> str:
    weather, news, videos = await asyncio.gather(
        fetch_weather(region, log),
        fetch_news(region, log),
        fetch_youtube(region, log),
    )

    parts = [f"📍 *GeoIntel Report: {region}*\n", weather]

    if news:
        parts.append("\n\n📰 *Top Headlines*")
        for title, link in news:
            short = title[:80] + ("…" if len(title) > 80 else "")
            parts.append(f"• [{short}]({link})")
    else:
        parts.append("\n\n📰 No headlines found\\.")

    if videos:
        parts.append("\n\n🎥 *Related Videos*")
        for title, link in videos:
            short = title[:70] + ("…" if len(title) > 70 else "")
            parts.append(f"• [{short}]({link})")
    else:
        parts.append("\n\n🎥 _YouTube key not configured — add YOUTUBE\\_API\\_KEY to \\.env_")

    return "\n".join(parts)


async def send_log_file(context: ContextTypes.DEFAULT_TYPE, chat_id: int, log: BotSessionLog):
    """Send the session log as a .txt file to the user."""
    try:
        filename = f"geointel_bot_{log.region.replace(' ', '_').lower()}_{int(log.start_ts)}.txt"
        log_bytes = log.to_text().encode("utf-8")
        await context.bot.send_document(
            chat_id=chat_id,
            document=log_bytes,
            filename=filename,
            caption=f"Session log — {log.region}",
        )
        logger.info(f"Log file sent to chat {chat_id}: {filename}")
    except Exception as e:
        logger.warning(f"Failed to send log file: {e}")


# ── Handlers ───────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🌍 *GeoIntel Bot*\n\n"
        "Send any country or region name and I'll reply with:\n"
        "• 🌡 Current weather\n"
        "• 📰 Top 3 news headlines\n"
        "• 🎥 3 YouTube video links\n"
        "• 📄 Full session log as .txt file\n\n"
        "Examples: `Middle East`, `Ukraine`, `Taiwan`, `West Africa`",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, context)


async def handle_region(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    region = update.message.text.strip()
    if not region:
        return

    chat_id = update.message.chat_id
    log = BotSessionLog(region, chat_id)

    thinking = await update.message.reply_text(
        f"🔍 Fetching intel for *{region}*\\.\\.\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )

    success = False
    try:
        reply = await build_reply(region, log)
        await thinking.edit_text(reply, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        tracker.record_telegram_message(chat_id=chat_id)
        success = True
    except Exception as e:
        logger.error(f"handle_region error for '{region}': {e}")
        log._step(f"HANDLER ERROR: {e}")
        await thinking.edit_text(
            f"⚠️ Error fetching data for *{region}*: `{str(e)[:200]}`",
            parse_mode=ParseMode.MARKDOWN,
        )

    log.finish(success)
    await send_log_file(context, chat_id, log)


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("❌  TELEGRAM_BOT_TOKEN is not set in .env")
        print("    Create a bot via @BotFather on Telegram, then add the token to .env")
        return

    print("🤖 GeoIntel Telegram Bot starting…")
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_region))

    print("✅ Bot is running. Send a region name in Telegram.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
