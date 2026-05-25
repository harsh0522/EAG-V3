"""9-tool MCP server for assignment6.
Tools: web_search, fetch_url, get_time, currency_convert,
       read_file, list_dir, create_file, update_file, edit_file
File tools are sandboxed under ./sandbox/
"""
import asyncio
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Single .env source of truth
load_dotenv(Path(__file__).parent / ".env")

mcp = FastMCP("assignment6-tools")

SANDBOX = Path(__file__).parent / "sandbox"
SANDBOX.mkdir(exist_ok=True)


def _sandbox(path: str) -> Path:
    """Resolve path relative to sandbox, prevent path traversal."""
    resolved = (SANDBOX / path.lstrip("/")).resolve()
    if not str(resolved).startswith(str(SANDBOX.resolve())):
        raise ValueError(f"Path {path!r} escapes sandbox")
    return resolved


# ─── web_search ──────────────────────────────────────────────────────────────

@mcp.tool()
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web. Uses Tavily if TAVILY_API_KEY is set, else DuckDuckGo."""
    max_results = min(max_results, 5)
    tavily_key = os.getenv("TAVILY_API_KEY")
    if tavily_key:
        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=tavily_key)
            resp = client.search(query, max_results=max_results, search_depth="advanced")
            results = resp.get("results", [])
            lines = []
            for r in results:
                lines.append(f"[{r.get('title','')}]({r.get('url','')})\n{r.get('content','')[:300]}")
            return "\n\n".join(lines) if lines else "No results found."
        except Exception as e:
            print(f"[mcp] Tavily error: {e}, falling back to DDG", file=sys.stderr)

    # DuckDuckGo fallback
    try:
        from duckduckgo_search import DDGS
        results = list(DDGS().text(query, max_results=max_results))
        lines = []
        for r in results:
            lines.append(f"[{r.get('title','')}]({r.get('href','')})\n{r.get('body','')[:300]}")
        return "\n\n".join(lines) if lines else "No results found."
    except Exception as e:
        return f"Search failed: {e}"


# ─── fetch_url ───────────────────────────────────────────────────────────────

@mcp.tool()
def fetch_url(url: str) -> str:
    """Fetch a URL and return clean markdown text using crawl4ai."""
    try:
        return _fetch_with_crawl4ai(url)
    except Exception as e:
        print(f"[mcp] crawl4ai error: {e}, falling back to httpx", file=sys.stderr)
        return _fetch_with_httpx(url)


def _fetch_with_crawl4ai(url: str) -> str:
    import asyncio as _aio

    async def _crawl():
        from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
        browser_cfg = BrowserConfig(headless=True, verbose=False)
        run_cfg = CrawlerRunConfig(word_count_threshold=10, excluded_tags=["nav", "footer", "header"])
        async with AsyncWebCrawler(config=browser_cfg) as crawler:
            result = await crawler.arun(url=url, config=run_cfg)
            if result.success:
                return result.markdown.raw_markdown if hasattr(result.markdown, "raw_markdown") else str(result.markdown)
            return f"Crawl failed: {result.error_message}"

    try:
        loop = _aio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(_aio.run, _crawl())
                return future.result(timeout=120)
        else:
            return loop.run_until_complete(_crawl())
    except Exception as e:
        raise RuntimeError(f"crawl4ai failed: {e}") from e


def _fetch_with_httpx(url: str) -> str:
    import httpx
    headers = {"User-Agent": "Mozilla/5.0 (compatible; assignment6-agent/1.0)"}
    r = httpx.get(url, headers=headers, follow_redirects=True, timeout=30)
    r.raise_for_status()
    text = r.text
    # Strip HTML tags
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:50000]


# ─── get_time ────────────────────────────────────────────────────────────────

@mcp.tool()
def get_time(timezone_name: str = "UTC") -> str:
    """Return the current time in the given timezone."""
    try:
        import zoneinfo
        tz = zoneinfo.ZoneInfo(timezone_name)
        now = datetime.now(tz)
        return now.strftime(f"%Y-%m-%d %H:%M:%S %Z (UTC%z)")
    except Exception:
        now = datetime.now(timezone.utc)
        return now.strftime("%Y-%m-%d %H:%M:%S UTC")


# ─── currency_convert ────────────────────────────────────────────────────────

@mcp.tool()
def currency_convert(amount: float, from_currency: str, to_currency: str) -> str:
    """Convert an amount between currencies using a free exchange rate API."""
    try:
        import httpx
        from_c = from_currency.upper()
        to_c = to_currency.upper()
        r = httpx.get(
            f"https://api.exchangerate-api.com/v4/latest/{from_c}",
            timeout=10,
        )
        r.raise_for_status()
        data = r.json()
        rates = data.get("rates", {})
        if to_c not in rates:
            return f"Currency {to_c} not found in exchange rates."
        converted = amount * rates[to_c]
        return f"{amount} {from_c} = {converted:.4f} {to_c} (rate: {rates[to_c]})"
    except Exception as e:
        return f"Currency conversion failed: {e}"


# ─── read_file ───────────────────────────────────────────────────────────────

@mcp.tool()
def read_file(path: str) -> str:
    """Read a file from the sandbox directory."""
    try:
        p = _sandbox(path)
        if not p.exists():
            return f"File not found: {path}"
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Error reading file: {e}"


# ─── list_dir ────────────────────────────────────────────────────────────────

@mcp.tool()
def list_dir(path: str = ".") -> str:
    """List files in a sandbox directory."""
    try:
        p = _sandbox(path)
        if not p.exists():
            return f"Directory not found: {path}"
        entries = []
        for item in sorted(p.iterdir()):
            kind = "dir" if item.is_dir() else "file"
            size = item.stat().st_size if item.is_file() else 0
            entries.append(f"{kind}: {item.name} ({size} bytes)")
        return "\n".join(entries) if entries else "(empty directory)"
    except Exception as e:
        return f"Error listing directory: {e}"


# ─── create_file ─────────────────────────────────────────────────────────────

@mcp.tool()
def create_file(path: str, content: str) -> str:
    """Create a new file in the sandbox. Parent directories are created automatically."""
    try:
        p = _sandbox(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():
            return f"File already exists: {path}. Use update_file to overwrite."
        p.write_text(content, encoding="utf-8")
        return f"Created {path} ({len(content.encode())} bytes)"
    except Exception as e:
        return f"Error creating file: {e}"


# ─── update_file ─────────────────────────────────────────────────────────────

@mcp.tool()
def update_file(path: str, content: str) -> str:
    """Overwrite an existing file in the sandbox with new content."""
    try:
        p = _sandbox(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Updated {path} ({len(content.encode())} bytes)"
    except Exception as e:
        return f"Error updating file: {e}"


# ─── edit_file ───────────────────────────────────────────────────────────────

@mcp.tool()
def edit_file(path: str, old_text: str, new_text: str) -> str:
    """Replace the first occurrence of old_text with new_text in a sandbox file."""
    try:
        p = _sandbox(path)
        if not p.exists():
            return f"File not found: {path}"
        content = p.read_text(encoding="utf-8")
        if old_text not in content:
            return f"old_text not found in {path}"
        updated = content.replace(old_text, new_text, 1)
        p.write_text(updated, encoding="utf-8")
        return f"Edited {path}: replaced {len(old_text)} chars with {len(new_text)} chars"
    except Exception as e:
        return f"Error editing file: {e}"


if __name__ == "__main__":
    mcp.run()
