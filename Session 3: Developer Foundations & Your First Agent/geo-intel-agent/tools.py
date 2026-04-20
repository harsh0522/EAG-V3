import httpx
import feedparser
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
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://finance.yahoo.com/",
    }
    urls = [
        "https://query2.finance.yahoo.com/v8/finance/chart/CL%3DF?interval=1d&range=5d",
        "https://query1.finance.yahoo.com/v8/finance/chart/CL%3DF?interval=1d&range=5d",
        "https://query2.finance.yahoo.com/v7/finance/quote?symbols=CL%3DF",
    ]

    data = {}
    error = None
    used_url = urls[0]

    for url in urls:
        try:
            async with httpx.AsyncClient(timeout=15, headers=headers, follow_redirects=True) as client:
                resp = await client.get(url)
            if resp.status_code != 200:
                continue
            raw = resp.json()
            used_url = url

            # v8 chart endpoint
            if "chart" in raw:
                meta = raw["chart"]["result"][0]["meta"]
                price = round(float(meta["regularMarketPrice"]), 2)
                prev_price = round(float(meta.get("previousClose") or meta.get("chartPreviousClose", price)), 2)
            # v7 quote endpoint
            elif "quoteResponse" in raw:
                result = raw["quoteResponse"]["result"][0]
                price = round(float(result["regularMarketPrice"]), 2)
                prev_price = round(float(result.get("regularMarketPreviousClose", price)), 2)
            else:
                continue

            change_pct = round(((price - prev_price) / prev_price) * 100, 2) if prev_price else 0.0
            data = {
                "symbol": "CL=F",
                "name": "WTI Crude Oil",
                "price_usd": price,
                "prev_close_usd": prev_price,
                "change_pct": change_pct,
            }
            error = None
            break
        except Exception as e:
            error = str(e)

    return {
        "url": used_url,
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
        model = genai.GenerativeModel("gemini-2.5-flash-lite")
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
