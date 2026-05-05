#!/usr/bin/env python3
"""
Company Intelligence Agent
Connects to the MCP server, uses Gemini 2.0 Flash as the brain,
and runs a ReAct loop to fetch, save, and display company data.
"""

import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime, timezone

import google.genai as genai
from google.genai import types
from fastmcp import Client
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8000/sse")
GEMINI_MODEL = "gemini-2.0-flash"
MAX_ITERATIONS = 15

DEMO_PROMPT = (
    "Fetch detailed information about Reliance Industries and Infosys from the web. "
    "For each company, also include financial data you know: ticker symbol, approximate "
    "current share price, 5-year CAGR (%), and market cap. Save each company to the "
    "local data file. Then show both companies on the Prefab dashboard in comparison mode."
)

SYSTEM_PROMPT = """You are a Company Intelligence Agent with access to 3 powerful tools:

1. fetch_company_info(company_name) — Searches the web (Wikipedia + DuckDuckGo) and
   returns a structured dict with description, summary, founded year, key people,
   industry, and source URL.

2. company_file_crud(operation, company_name, data) — Manages a local company database.
   Operations: create / read / update / delete / list.
   Use "create" to save a new company, "update" if it already exists.

3. show_on_dashboard(companies_data, mode) — Generates a live Prefab UI dashboard and
   serves it at http://127.0.0.1:5175. Use mode="comparison" for multiple companies.

WORKFLOW A — when user says "fetch" or does NOT say "use your knowledge only":
  Step 1 — Call fetch_company_info for each company to get web data.
  Step 2 — Enrich the fetched dict with financial data from your own knowledge:
           ticker, share_price, cagr_5yr_pct, market_cap.
  Step 3 — Call company_file_crud with the enriched dict (create or update).
  Step 4 — After ALL companies saved, call show_on_dashboard once.

WORKFLOW B — when user says "use LLM knowledge", "no fetch", or "skip fetch":
  Step 1 — SKIP fetch_company_info entirely. Use your training knowledge to build
           the full company dict with ALL fields:
           description, summary, industry, founded, key_people, source_url,
           ticker, share_price, cagr_5yr_pct, market_cap.
  Step 2 — Call company_file_crud directly (create or update).
  Step 3 — After ALL companies saved, call show_on_dashboard once.

RULES:
  • Financial fields: ticker (e.g. "JIOFIN.NS"), share_price (e.g. "340 INR"),
    cagr_5yr_pct (e.g. 12.5), market_cap (e.g. "2.2T INR").
  • If a company is private/unlisted, set ticker="N/A (private)", share_price="N/A (unlisted)", cagr_5yr_pct=null, market_cap="N/A".
  • If create fails with "already exists", immediately retry with operation="update".
  • Be concise in final summaries — the dashboard shows everything visually.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Tool schema conversion
# ─────────────────────────────────────────────────────────────────────────────

# Gemini only accepts this subset of JSON Schema fields in function declarations.
_GEMINI_SCHEMA_KEYS = {"type", "properties", "required", "description", "enum", "items", "anyOf"}


def _clean_schema(schema) -> dict:
    """Recursively strip JSON Schema fields that Gemini rejects (e.g. additionalProperties)."""
    if not isinstance(schema, dict):
        return schema
    cleaned = {}
    for key, value in schema.items():
        if key not in _GEMINI_SCHEMA_KEYS:
            continue
        if key == "properties" and isinstance(value, dict):
            cleaned[key] = {k: _clean_schema(v) for k, v in value.items()}
        elif key == "items" and isinstance(value, dict):
            cleaned[key] = _clean_schema(value)
        elif key == "anyOf" and isinstance(value, list):
            cleaned[key] = [_clean_schema(s) for s in value]
        else:
            cleaned[key] = value
    return cleaned


def _mcp_tool_to_gemini(tool) -> dict:
    """Convert an MCP Tool object to a Gemini function declaration dict."""
    schema: dict = {}
    if hasattr(tool, "inputSchema") and tool.inputSchema:
        schema = dict(tool.inputSchema)
    elif hasattr(tool, "parameters") and tool.parameters:
        schema = dict(tool.parameters)

    if not schema:
        schema = {"type": "object", "properties": {}}

    return {
        "name": tool.name,
        "description": tool.description or f"Tool: {tool.name}",
        "parameters": _clean_schema(schema),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Result extraction
# ─────────────────────────────────────────────────────────────────────────────
def _extract_tool_result(raw) -> dict:
    """Parse whatever FastMCP returns into a Python dict."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        text_parts = []
        for item in raw:
            if hasattr(item, "text"):
                text_parts.append(item.text)
            elif hasattr(item, "content"):
                text_parts.append(str(item.content))
            else:
                text_parts.append(str(item))
        combined = "".join(text_parts)
        try:
            return json.loads(combined)
        except json.JSONDecodeError:
            return {"output": combined}
    try:
        return json.loads(str(raw))
    except (json.JSONDecodeError, TypeError):
        return {"output": str(raw)}


# ─────────────────────────────────────────────────────────────────────────────
# Pretty print helpers
# ─────────────────────────────────────────────────────────────────────────────
def _banner(label: str, width: int = 60):
    print(f"\n{'─' * width}")
    print(f"  {label}")
    print(f"{'─' * width}")


def _print_tool_call(name: str, args: dict):
    args_str = json.dumps(args, indent=2, default=str)
    print(f"\n[TOOL CALL] {name}")
    print(args_str)


def _print_tool_result(result: dict):
    result_str = json.dumps(result, indent=2, default=str)
    # Truncate very long results for readability
    if len(result_str) > 800:
        result_str = result_str[:800] + "\n  … (truncated)"
    print(f"[TOOL RESULT]\n{result_str}")


# ─────────────────────────────────────────────────────────────────────────────
# Core ReAct loop
# ─────────────────────────────────────────────────────────────────────────────
async def run_agent(prompt: str):
    if not GEMINI_API_KEY:
        print("[ERROR] GEMINI_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    _banner(f"Company Intelligence Agent  |  {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"Prompt: {prompt}")
    print(f"MCP Server: {MCP_SERVER_URL}")
    print(f"Model: {GEMINI_MODEL}  |  Max iterations: {MAX_ITERATIONS}")

    # ── Connect to MCP ─────────────────────────────────────────────────────────
    print("\nConnecting to MCP server…", end=" ", flush=True)
    try:
        async with Client(MCP_SERVER_URL) as mcp_client:
            print("Connected.")

            # Discover tools
            mcp_tools = await mcp_client.list_tools()
            print(f"Discovered {len(mcp_tools)} tools: {[t.name for t in mcp_tools]}")

            gemini_declarations = [_mcp_tool_to_gemini(t) for t in mcp_tools]
            gemini_tools = [types.Tool(function_declarations=gemini_declarations)]

            # ── Set up Gemini ──────────────────────────────────────────────────
            gemini_client = genai.Client(api_key=GEMINI_API_KEY)

            # Build initial message list
            messages = [
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=f"{SYSTEM_PROMPT}\n\nUser request: {prompt}")],
                )
            ]

            tool_call_count = 0
            final_text = ""

            # ── ReAct loop ─────────────────────────────────────────────────────
            for iteration in range(1, MAX_ITERATIONS + 1):
                _banner(f"Iteration {iteration}/{MAX_ITERATIONS}")

                # Call Gemini — retry up to 3× on 429 with backoff
                response = None
                for attempt in range(3):
                    try:
                        response = await gemini_client.aio.models.generate_content(
                            model=GEMINI_MODEL,
                            contents=messages,
                            config=types.GenerateContentConfig(
                                tools=gemini_tools,
                                temperature=0.1,
                            ),
                        )
                        break
                    except Exception as api_err:
                        err_str = str(api_err)
                        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "503" in err_str or "UNAVAILABLE" in err_str:
                            m = re.search(r"retry in (\d+)", err_str)
                            wait = int(m.group(1)) + 2 if m else (10 * (attempt + 1))
                            print(f"[RETRY] {err_str[:60]} — attempt {attempt+1}/3, waiting {wait}s…")
                            await asyncio.sleep(wait)
                        else:
                            raise
                if response is None:
                    print("[ERROR] Gemini failed after 3 retries (quota exhausted). Stopping.")
                    break

                candidate = response.candidates[0]
                content = candidate.content

                # Collect text parts for display
                text_parts = [p.text for p in content.parts if hasattr(p, "text") and p.text]
                if text_parts:
                    print(f"[GEMINI] {' '.join(text_parts)}")

                # Check finish reason
                finish_reason = str(candidate.finish_reason) if candidate.finish_reason else ""
                has_function_calls = any(
                    hasattr(p, "function_call") and p.function_call
                    for p in content.parts
                )

                if not has_function_calls:
                    # Agent is done
                    final_text = " ".join(text_parts)
                    print("\n[AGENT] No more tool calls — task complete.")
                    break

                # Add model response to history
                messages.append(content)

                # Execute all function calls in this response
                function_response_parts = []
                for part in content.parts:
                    if not (hasattr(part, "function_call") and part.function_call):
                        continue

                    fc = part.function_call
                    tool_name = fc.name
                    tool_args = dict(fc.args) if fc.args else {}

                    tool_call_count += 1
                    _print_tool_call(tool_name, tool_args)

                    # Execute tool via MCP
                    try:
                        raw_result = await mcp_client.call_tool(tool_name, tool_args)
                        result_dict = _extract_tool_result(raw_result)
                    except Exception as e:
                        result_dict = {"status": "error", "message": str(e)}
                        print(f"[MCP ERROR] Tool '{tool_name}' raised: {e}", file=sys.stderr)

                    _print_tool_result(result_dict)

                    function_response_parts.append(
                        types.Part.from_function_response(
                            name=tool_name,
                            response={"output": json.dumps(result_dict, default=str)},
                        )
                    )

                # Add all function results in one user turn
                if function_response_parts:
                    messages.append(
                        types.Content(role="user", parts=function_response_parts)
                    )

                if tool_call_count >= MAX_ITERATIONS:
                    print(f"\n[AGENT] Reached max tool call limit ({MAX_ITERATIONS}). Stopping.")
                    break

            else:
                print(f"\n[AGENT] Reached max iterations ({MAX_ITERATIONS}).")

            # ── Final summary ──────────────────────────────────────────────────
            _banner("Final Summary")
            if final_text:
                print(final_text)
            else:
                print(f"Completed {tool_call_count} tool call(s).")
            print(f"\nDashboard → http://127.0.0.1:5175")

    except ConnectionRefusedError:
        print(
            "\n[ERROR] Cannot connect to MCP server at "
            f"{MCP_SERVER_URL}\n"
            "Make sure you ran:  python mcp_server.py  in Terminal 1."
        )
        sys.exit(1)
    except Exception as e:
        print(f"\n[ERROR] Unexpected error: {e}")
        raise


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────
def main():
    if len(sys.argv) > 1:
        prompt = " ".join(sys.argv[1:])
    else:
        print(f"\nDemo prompt:\n  {DEMO_PROMPT}\n")
        user_input = input("Enter prompt (or press Enter to use demo): ").strip()
        prompt = user_input if user_input else DEMO_PROMPT

    asyncio.run(run_agent(prompt))


if __name__ == "__main__":
    main()
