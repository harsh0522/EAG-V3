"""MCP server for assignment7.

Tools:
  web_search, fetch_url, get_time, currency_convert,
  read_file, list_dir, create_file, update_file, edit_file,
  index_document, search_knowledge          ← new in S7

File tools are sandboxed under ./sandbox/
index_document reads from the project root (papers/, corpus/, sandbox/)
"""
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv(Path(__file__).parent.parent / ".env")  # Session 7 root .env

mcp = FastMCP("assignment7-tools")

_ROOT = Path(__file__).parent  # assignment7/
SANDBOX = _ROOT / "sandbox"
SANDBOX.mkdir(exist_ok=True)

# ─── Shared memory instance for MCP subprocess ────────────────────────────────
# Imported here so index_document and search_knowledge can persist to state/
import memory as _mem_module
_memory = _mem_module.Memory()


def _sandbox(path: str) -> Path:
    """Resolve path relative to sandbox, prevent path traversal."""
    resolved = (SANDBOX / path.lstrip("/")).resolve()
    if not str(resolved).startswith(str(SANDBOX.resolve())):
        raise ValueError(f"Path {path!r} escapes sandbox")
    return resolved


def _project_path(path: str) -> Path:
    """Resolve path relative to assignment7 root for index_document reads."""
    resolved = (_ROOT / path.lstrip("/")).resolve()
    if not str(resolved).startswith(str(_ROOT.resolve())):
        raise ValueError(f"Path {path!r} escapes project root")
    return resolved


# ─── Chunking helpers ─────────────────────────────────────────────────────────

def _sliding_window(text: str, chunk_size: int, overlap: int) -> list[str]:
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end == len(words):
            break
        start = end - overlap
    return chunks


_STOPWORDS = {
    "a", "an", "the", "is", "it", "its", "in", "on", "at", "to", "of", "and",
    "or", "for", "with", "this", "that", "be", "was", "are", "were",
}


def _extract_keywords(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    filtered = [t for t in tokens if t not in _STOPWORDS and len(t) > 2]
    freq: dict[str, int] = {}
    for t in filtered:
        freq[t] = freq.get(t, 0) + 1
    return [w for w, _ in sorted(freq.items(), key=lambda x: -x[1])[:10]]


def _current_run_id() -> str:
    return _mem_module.Memory.get_current_run()


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
    headers = {"User-Agent": "Mozilla/5.0 (compatible; assignment7-agent/1.0)"}
    r = httpx.get(url, headers=headers, follow_redirects=True, timeout=30)
    r.raise_for_status()
    text = r.text
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
        r = httpx.get(f"https://api.exchangerate-api.com/v4/latest/{from_c}", timeout=10)
        r.raise_for_status()
        rates = r.json().get("rates", {})
        if to_c not in rates:
            return f"Currency {to_c} not found in exchange rates."
        converted = amount * rates[to_c]
        return f"{amount} {from_c} = {converted:.4f} {to_c} (rate: {rates[to_c]})"
    except Exception as e:
        return f"Currency conversion failed: {e}"


# ─── read_file ───────────────────────────────────────────────────────────────

@mcp.tool()
def read_file(path: str) -> str:
    """Read a file for one-shot inspection. Reads from sandbox/, papers/, or corpus/.
    For files that should be searchable later, use index_document instead."""
    try:
        if path.startswith("papers") or path.startswith("corpus"):
            p = _project_path(path)
        else:
            p = _sandbox(path)
        if not p.exists():
            return f"File not found: {path}"
        return p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"Error reading file: {e}"


# ─── list_dir ────────────────────────────────────────────────────────────────

@mcp.tool()
def list_dir(path: str = ".") -> str:
    """List files in a directory. Use '.' for sandbox, 'papers/' or 'corpus/' for project dirs."""
    try:
        # Allow listing project-level dirs for papers/ and corpus/
        if path.startswith("papers") or path.startswith("corpus"):
            p = _project_path(path)
        else:
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
    """Create a new file in the sandbox."""
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


# ─── index_document ──────────────────────────────────────────────────────────

@mcp.tool()
def index_document(path: str, chunk_size: int = 400, overlap: int = 80) -> dict:
    """Chunk a project file and write the chunks into Memory as fact records,
    where they become FAISS-searchable for later queries.

    Use this when the content must be searchable across later turns or runs.
    For one-shot inspection of a file's contents, use read_file instead.

    path: project-relative path (e.g. 'papers/attention.md', 'corpus/lora.md').
    chunk_size: words per chunk, default 400.
    overlap: words of overlap between chunks, default 80.

    Returns: {"path": str, "chunks_indexed": int}
    """
    try:
        p = _project_path(path)
        if not p.exists():
            return {"error": f"File not found: {path}", "path": path, "chunks_indexed": 0}
        text = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return {"error": str(e), "path": path, "chunks_indexed": 0}

    chunks = _sliding_window(text, chunk_size, overlap)
    run_id = _current_run_id()

    for i, chunk_text in enumerate(chunks):
        descriptor = f"[{path} chunk {i+1}/{len(chunks)}]"
        _memory.add_fact(
            descriptor=descriptor,
            value={"chunk": chunk_text, "source": path,
                   "chunk_index": i, "total_chunks": len(chunks)},
            keywords=_extract_keywords(chunk_text),
            source=f"index_document:{path}",
            run_id=run_id,
        )

    return {"path": path, "chunks_indexed": len(chunks)}


# ─── search_knowledge ────────────────────────────────────────────────────────

@mcp.tool()
def search_knowledge(query: str, k: int = 5) -> list[dict]:
    """Vector search over previously indexed fact chunks. Use this rather than
    re-fetching or re-reading source files when Memory already contains indexed
    chunks for the topic.

    Use this when you need to find relevant passages from indexed documents.
    For fresh content not yet indexed, use fetch_url or read_file instead.

    query: natural language query.
    k: number of chunks to return, default 5.

    Returns a list of {"chunk": str, "source": str, "chunk_index": int,
    "score": float}, ranked by relevance.
    """
    hits = _memory.read(query, k=k)
    facts = [h for h in hits if h.kind == "fact"]
    return [
        {
            "chunk": h.value.get("chunk", ""),
            "source": h.value.get("source", h.source),
            "chunk_index": h.value.get("chunk_index", 0),
            "score": round(h.score, 4),
        }
        for h in facts
    ]


if __name__ == "__main__":
    mcp.run()
