"""
GeoIntel Telegram Bot
Send any region/country name → get weather, top news, and YouTube links.
"""

import asyncio
import os

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


# ── Data fetchers ──────────────────────────────────────────────────────────────

async def fetch_weather(region: str) -> str:
    """wttr.in — free, no API key needed. Handles city names, regions, coordinates."""
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            r = await client.get(
                f"https://wttr.in/{region}?format=j1",
                headers={"User-Agent": "GeoIntelBot/1.0"},
            )
        d = r.json()
        cur = d["current_condition"][0]
        desc = cur["weatherDesc"][0]["value"]
        temp_c = cur["temp_C"]
        temp_f = cur["temp_F"]
        feels = cur["FeelsLikeC"]
        humidity = cur["humidity"]
        wind_kmph = cur["windspeedKmph"]
        nearest = d.get("nearest_area", [{}])[0]
        area = nearest.get("areaName", [{}])[0].get("value", region)
        country = nearest.get("country", [{}])[0].get("value", "")

        location_str = f"{area}, {country}" if country else area
        return (
            f"🌡 *Weather near {location_str}*\n"
            f"{desc}  •  {temp_c}°C / {temp_f}°F\n"
            f"Feels like: {feels}°C  •  Humidity: {humidity}%\n"
            f"Wind: {wind_kmph} km/h"
        )
    except Exception as e:
        return f"🌡 Weather unavailable for _{region}_ (wttr.in error)"


async def fetch_news(region: str) -> list[tuple[str, str]]:
    """Google News RSS — top 3 headlines, no API key needed."""
    url = (
        f"https://news.google.com/rss/search"
        f"?q={region}&hl=en-US&gl=US&ceid=US:en"
    )
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            r = await client.get(url)
        feed = feedparser.parse(r.text)
        return [(e.title, e.link) for e in feed.entries[:3]]
    except Exception:
        return []


async def fetch_youtube(region: str) -> list[tuple[str, str]]:
    """YouTube Data API v3 — 3 videos. Requires YOUTUBE_API_KEY."""
    if not YOUTUBE_API_KEY or YOUTUBE_API_KEY == "YOUR_YOUTUBE_API_KEY_HERE":
        return []
    url = (
        "https://www.googleapis.com/youtube/v3/search"
        f"?part=snippet&q={region}+geopolitics&maxResults=3&type=video&key={YOUTUBE_API_KEY}"
    )
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(url)
        items = r.json().get("items", [])
        return [
            (item["snippet"]["title"], f"https://youtu.be/{item['id']['videoId']}")
            for item in items
        ]
    except Exception:
        return []


# ── Message builder ────────────────────────────────────────────────────────────

def escape_md(text: str) -> str:
    """Escape special chars for Telegram MarkdownV2."""
    for ch in r"\_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text


async def build_reply(region: str) -> str:
    weather, news, videos = await asyncio.gather(
        fetch_weather(region),
        fetch_news(region),
        fetch_youtube(region),
    )

    parts = [f"📍 *GeoIntel Report: {region}*\n", weather]

    if news:
        parts.append("\n\n📰 *Top Headlines*")
        for title, link in news:
            # Truncate long titles
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


# ── Handlers ───────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🌍 *GeoIntel Bot*\n\n"
        "Send any country or region name and I'll reply with:\n"
        "• 🌡 Current weather\n"
        "• 📰 Top 3 news headlines\n"
        "• 🎥 3 YouTube video links\n\n"
        "Examples: `Middle East`, `Ukraine`, `Taiwan`, `West Africa`",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, context)


async def handle_region(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    region = update.message.text.strip()
    if not region:
        return

    # Acknowledge quickly
    thinking = await update.message.reply_text(
        f"🔍 Fetching intel for *{region}*\\.\\.\\.",
        parse_mode=ParseMode.MARKDOWN_V2,
    )

    try:
        reply = await build_reply(region)
        await thinking.edit_text(reply, parse_mode=ParseMode.MARKDOWN, disable_web_page_preview=True)
        tracker.record_telegram_message(chat_id=update.message.chat_id)
    except Exception as e:
        await thinking.edit_text(
            f"⚠️ Error fetching data for *{region}*: `{str(e)[:200]}`",
            parse_mode=ParseMode.MARKDOWN,
        )


# ── Entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        print("❌  TELEGRAM_BOT_TOKEN is not set in .env")
        print("    Create a bot via @BotFather on Telegram, then add the token to .env")
        return

    print("🤖 GeoIntel Telegram Bot starting…")
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_region))

    print("✅ Bot is running. Send a region name in Telegram.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
