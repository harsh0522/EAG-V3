import httpx
import feedparser
import yfinance as yf
import json
import time
import os
import google.generativeai as genai
from usage_tracker import tracker


async def get_geopolitical_news(region: str) -> dict:
    start_time = time.time()
    url = f"https://news.google.com/rss/search?q={region}+geopolitics+conflict+economy&hl=en-US&gl=US&ceid=US:en"

    try:
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url)
        feed = feedparser.parse(resp.text)
        articles = []
        for entry in feed.entries[:10]:
            articles.append({
                "title": entry.title,
                "link": entry.link,
                "published": entry.get("published", ""),
                "summary": entry.get("summary", "")[:300],
            })
        data = {"region": region, "articles": articles, "count": len(articles)}
        error = None
    except Exception as e:
        data = {"region": region, "articles": [], "count": 0}
        error = str(e)

    return {
        "url": url,
        "method": "GET",
        "response_time_ms": round((time.time() - start_time) * 1000, 1),
        "data": data,
        "error": error,
    }


async def get_fear_greed_index() -> dict:
    start_time = time.time()
    url = "https://api.alternative.me/fng/?limit=1"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
        data = resp.json()
        error = None
    except Exception as e:
        data = {}
        error = str(e)

    return {
        "url": url,
        "method": "GET",
        "response_time_ms": round((time.time() - start_time) * 1000, 1),
        "data": data,
        "error": error,
    }


async def get_oil_prices() -> dict:
    start_time = time.time()
    url_label = "yahoo_finance:CL=F (WTI Crude Oil Futures)"

    try:
        ticker = yf.Ticker("CL=F")
        hist = ticker.history(period="5d")
        if hist.empty:
            raise ValueError("No price data returned")

        latest = hist.iloc[-1]
        prev = hist.iloc[-2] if len(hist) > 1 else hist.iloc[0]
        price = round(float(latest["Close"]), 2)
        prev_price = round(float(prev["Close"]), 2)
        change_pct = round(((price - prev_price) / prev_price) * 100, 2)

        data = {
            "symbol": "CL=F",
            "name": "WTI Crude Oil",
            "price_usd": price,
            "prev_close_usd": prev_price,
            "change_pct": change_pct,
            "volume": int(latest.get("Volume", 0)),
        }
        error = None
    except Exception as e:
        data = {}
        error = str(e)

    return {
        "url": url_label,
        "method": "GET",
        "response_time_ms": round((time.time() - start_time) * 1000, 1),
        "data": data,
        "error": error,
    }


async def predict_oil_trend(news: str, sentiment: str, prices: str) -> dict:
    start_time = time.time()

    prompt = f"""You are an expert oil market analyst. Based on the following data, predict the short-term (48-hour) crude oil price trend.

GEOPOLITICAL NEWS:
{news[:1500]}

MARKET SENTIMENT (Fear & Greed Index):
{sentiment}

CURRENT OIL PRICES:
{prices}

Provide a structured analysis:
1. TREND DIRECTION: BULLISH / BEARISH / NEUTRAL
2. CONFIDENCE: HIGH / MEDIUM / LOW
3. KEY DRIVERS: (3-5 bullet points)
4. 48-HOUR PRICE RANGE PREDICTION: ($X - $Y)
5. RISK FACTORS TO WATCH: (2-3 bullet points)
6. OVERALL ASSESSMENT: (2-3 sentences)

Be concise and data-driven."""

    try:
        model = genai.GenerativeModel("gemini-2.0-flash-lite")
        response = await model.generate_content_async(prompt)
        tokens = response.usage_metadata.total_token_count if response.usage_metadata else 0
        tracker.record_gemini_call(tokens)
        data = {
            "analysis": response.text,
            "tokens_used": tokens,
        }
        error = None
    except Exception as e:
        data = {"analysis": "Analysis unavailable", "tokens_used": 0}
        error = str(e)

    return {
        "url": "internal:gemini_oil_trend_analysis",
        "method": "LLM_CALL",
        "response_time_ms": round((time.time() - start_time) * 1000, 1),
        "data": data,
        "error": error,
    }


async def get_youtube_videos(query: str) -> dict:
    start_time = time.time()
    api_key = os.getenv("YOUTUBE_API_KEY", "")

    if not api_key or api_key == "YOUR_YOUTUBE_API_KEY_HERE":
        return {
            "url": "youtube_data_api_v3:search",
            "method": "GET",
            "response_time_ms": 0,
            "data": {"query": query, "videos": [], "error": "YOUTUBE_API_KEY not configured"},
            "error": "Missing API key",
        }

    url = (
        f"https://www.googleapis.com/youtube/v3/search"
        f"?part=snippet&q={query}&maxResults=3&type=video&key={api_key}"
    )
    masked_url = url.replace(api_key, "***MASKED***")

    tracker.record_youtube_search()
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url)
        raw = resp.json()

        videos = []
        for item in raw.get("items", []):
            vid_id = item["id"]["videoId"]
            snip = item["snippet"]
            videos.append({
                "video_id": vid_id,
                "title": snip["title"],
                "description": snip.get("description", "")[:200],
                "thumbnail": snip["thumbnails"]["medium"]["url"],
                "embed_url": f"https://www.youtube.com/embed/{vid_id}",
            })

        data = {"query": query, "videos": videos}
        error = None
    except Exception as e:
        data = {"query": query, "videos": []}
        error = str(e)

    return {
        "url": masked_url,
        "method": "GET",
        "response_time_ms": round((time.time() - start_time) * 1000, 1),
        "data": data,
        "error": error,
    }
