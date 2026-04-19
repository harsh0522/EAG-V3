"""
Run this before starting the app or bot.
Tests every API key and free endpoint so no tokens get wasted on a broken config.

Usage:
    .venv/bin/python check_keys.py
"""

import asyncio
import os
import sys

import httpx
from dotenv import load_dotenv

load_dotenv()

PASS = "✅"
FAIL = "❌"
WARN = "⚠️ "

results = []


def report(label: str, ok: bool, detail: str = ""):
    icon = PASS if ok else FAIL
    msg = f"  {icon}  {label}"
    if detail:
        msg += f"  —  {detail}"
    print(msg)
    results.append(ok)


# ── Key presence checks (fast, no network) ────────────────────────────────────

def check_env_keys():
    print("\n── .env Keys Present ─────────────────────────────────────")

    gemini = os.getenv("GEMINI_API_KEY", "")
    report("GEMINI_API_KEY set", bool(gemini), gemini[:12] + "…" if gemini else "missing")

    yt = os.getenv("YOUTUBE_API_KEY", "")
    yt_ok = bool(yt) and yt != "YOUR_YOUTUBE_API_KEY_HERE"
    report("YOUTUBE_API_KEY set", yt_ok, yt[:12] + "…" if yt_ok else "not configured (YouTube panel will be empty)")

    tg = os.getenv("TELEGRAM_BOT_TOKEN", "")
    tg_ok = bool(tg) and tg != "YOUR_TELEGRAM_BOT_TOKEN_HERE"
    report("TELEGRAM_BOT_TOKEN set", tg_ok, tg[:12] + "…" if tg_ok else "not configured (bot won't start)")


# ── Live API checks ────────────────────────────────────────────────────────────

async def check_gemini():
    print("\n── Gemini API ────────────────────────────────────────────")
    key = os.getenv("GEMINI_API_KEY", "")
    if not key:
        report("Gemini reachable", False, "no key")
        return

    url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
        if r.status_code == 200:
            models = [m["name"] for m in r.json().get("models", []) if "gemini" in m["name"].lower()]
            report("Gemini API key valid", True, f"{len(models)} Gemini models available")
        elif r.status_code == 400:
            report("Gemini API key valid", False, "400 — API key invalid or Generative Language API not enabled")
        elif r.status_code == 403:
            report("Gemini API key valid", False, "403 — API not enabled for this project (enable it in Google Cloud Console)")
        else:
            report("Gemini API key valid", False, f"HTTP {r.status_code}")
    except Exception as e:
        report("Gemini reachable", False, str(e))


async def check_youtube():
    print("\n── YouTube Data API v3 ───────────────────────────────────")
    key = os.getenv("YOUTUBE_API_KEY", "")
    if not key or key == "YOUR_YOUTUBE_API_KEY_HERE":
        report("YouTube API key valid", False, "not configured — skipping live check")
        return

    url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q=test&maxResults=1&type=video&key={key}"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
        if r.status_code == 200:
            report("YouTube API key valid", True, "search endpoint responded OK")
        elif r.status_code == 400:
            report("YouTube API key valid", False, "400 — bad request")
        elif r.status_code == 403:
            data = r.json()
            reason = data.get("error", {}).get("errors", [{}])[0].get("reason", "forbidden")
            report("YouTube API key valid", False, f"403 — {reason} (check API is enabled or quota)")
        else:
            report("YouTube API key valid", False, f"HTTP {r.status_code}")
    except Exception as e:
        report("YouTube reachable", False, str(e))


async def check_telegram():
    print("\n── Telegram Bot API ──────────────────────────────────────")
    token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not token or token == "YOUR_TELEGRAM_BOT_TOKEN_HERE":
        report("Telegram bot token valid", False, "not configured — skipping live check")
        return

    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url)
        data = r.json()
        if data.get("ok"):
            bot = data["result"]
            report("Telegram bot token valid", True, f"@{bot['username']} ({bot['first_name']})")
        else:
            report("Telegram bot token valid", False, data.get("description", "unknown error"))
    except Exception as e:
        report("Telegram reachable", False, str(e))


async def check_free_apis():
    print("\n── Free APIs (no key needed) ─────────────────────────────")

    checks = [
        ("Google News RSS",      "https://news.google.com/rss/search?q=test&hl=en-US"),
        ("Fear & Greed Index",   "https://api.alternative.me/fng/?limit=1"),
        ("wttr.in (weather)",    "https://wttr.in/London?format=j1"),
        ("Yahoo Finance (oil)",  "https://query1.finance.yahoo.com/v8/finance/chart/CL%3DF?interval=1d&range=5d"),
    ]

    async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
        for label, url in checks:
            try:
                r = await client.get(url, headers={"User-Agent": "GeoIntelChecker/1.0"})
                if r.status_code == 200:
                    report(label, True, f"HTTP 200")
                else:
                    report(label, False, f"HTTP {r.status_code}")
            except Exception as e:
                report(label, False, str(e)[:80])


# ── Main ───────────────────────────────────────────────────────────────────────

async def main():
    print("=" * 56)
    print("  GeoIntel — API Key & Endpoint Checker")
    print("=" * 56)

    check_env_keys()
    await check_gemini()
    await check_youtube()
    await check_telegram()
    await check_free_apis()

    total = len(results)
    passed = sum(results)
    failed = total - passed

    print("\n" + "=" * 56)
    print(f"  {passed}/{total} checks passed", end="")
    if failed:
        print(f"  ({failed} failed — fix before running the app)")
    else:
        print("  — all good, safe to start!")
    print("=" * 56 + "\n")

    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
