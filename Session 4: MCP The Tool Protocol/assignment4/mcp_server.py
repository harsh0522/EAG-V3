#!/usr/bin/env python3
"""MCP Server for Company Intelligence Agent — 3 tools registered."""

import os
import sys
import json
import shutil
import time
import subprocess
import py_compile
import tempfile
import re
import base64
from datetime import datetime, timezone
from pathlib import Path
from collections import Counter

import requests
from fastmcp import FastMCP
from dotenv import load_dotenv

load_dotenv()

# ── Paths ──────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.resolve()
DATA_DIR = BASE_DIR / "data"
COMPANIES_FILE = DATA_DIR / "companies.json"
LOG_FILE = DATA_DIR / "agent_log.json"
GENERATED_APP = BASE_DIR / "generated_app.py"
PREFAB_LOG = BASE_DIR / "prefab_server.log"
PID_FILE = BASE_DIR / "prefab.pid"


# ── Data helpers ───────────────────────────────────────────────────────────────
def ensure_data_files():
    DATA_DIR.mkdir(exist_ok=True)
    if not COMPANIES_FILE.exists():
        COMPANIES_FILE.write_text(json.dumps({}, indent=2))
    if not LOG_FILE.exists():
        LOG_FILE.write_text(json.dumps([], indent=2))


def load_companies() -> dict:
    try:
        return json.loads(COMPANIES_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"[MCP] Warning: could not load companies.json: {e}", file=sys.stderr)
        return {}


def save_companies(data: dict):
    tmp = COMPANIES_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    tmp.replace(COMPANIES_FILE)


def load_logs() -> list:
    try:
        return json.loads(LOG_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"[MCP] Warning: could not load agent_log.json: {e}", file=sys.stderr)
        return []


def append_log(operation: str, company: str, tool: str):
    logs = load_logs()
    logs.append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation": operation,
            "company": company,
            "tool": tool,
        }
    )
    LOG_FILE.write_text(json.dumps(logs, indent=2, default=str, ensure_ascii=False), encoding="utf-8")


ensure_data_files()

# ── MCP Server ─────────────────────────────────────────────────────────────────
mcp = FastMCP("Company Intelligence MCP Server")


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 1 — Web Fetch
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def fetch_company_info(company_name: str) -> dict:
    """Fetch company information from Wikipedia and DuckDuckGo."""
    result = {
        "company": company_name,
        "description": None,
        "summary": None,
        "founded": None,
        "headquarters": None,
        "key_people": None,
        "industry": None,
        "source_url": None,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
    }

    headers = {"User-Agent": "CompanyIntelAgent/1.0 (educational project)"}

    # ── Wikipedia REST API ─────────────────────────────────────────────────────
    try:
        encoded = requests.utils.quote(company_name.replace(" ", "_"))
        wiki_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{encoded}"
        resp = requests.get(wiki_url, timeout=12, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            result["description"] = data.get("description", "")
            extract = data.get("extract", "")
            result["summary"] = extract[:600] if extract else ""
            result["source_url"] = (
                data.get("content_urls", {}).get("desktop", {}).get("page", "")
            )
            print(f"[MCP] Wikipedia hit for '{company_name}'", file=sys.stderr)
        else:
            print(f"[MCP] Wikipedia status {resp.status_code} for '{company_name}'", file=sys.stderr)
    except Exception as e:
        print(f"[MCP] Wikipedia fetch error for '{company_name}': {e}", file=sys.stderr)

    # ── DuckDuckGo Instant Answer API ─────────────────────────────────────────
    try:
        ddg_url = (
            f"https://api.duckduckgo.com/?q={requests.utils.quote(company_name)}"
            "&format=json&no_redirect=1&no_html=1&skip_disambig=1"
        )
        resp = requests.get(ddg_url, timeout=12, headers=headers)
        if resp.status_code == 200:
            data = resp.json()

            if not result["description"] and data.get("AbstractText"):
                result["description"] = data["AbstractText"][:300]
            if not result["summary"] and data.get("AbstractText"):
                result["summary"] = data["AbstractText"][:600]
            if not result["source_url"] and data.get("AbstractURL"):
                result["source_url"] = data["AbstractURL"]

            for item in data.get("Infobox", {}).get("content", []):
                label = item.get("label", "").lower()
                value = item.get("value", "")
                if not value:
                    continue
                if "founded" in label and not result["founded"]:
                    result["founded"] = value
                elif "headquarter" in label and not result["headquarters"]:
                    result["headquarters"] = value
                elif "industry" in label and not result["industry"]:
                    result["industry"] = value
                elif (
                    any(k in label for k in ["key people", "founder", "ceo", "chairman"])
                    and not result["key_people"]
                ):
                    result["key_people"] = value

            print(f"[MCP] DuckDuckGo hit for '{company_name}'", file=sys.stderr)
    except Exception as e:
        print(f"[MCP] DuckDuckGo fetch error for '{company_name}': {e}", file=sys.stderr)

    # ── Try to extract founded year from summary via regex ─────────────────────
    if not result["founded"] and result["summary"]:
        m = re.search(r"\bfounded\b[^.]*?\b(1[5-9]\d{2}|20\d{2})\b", result["summary"], re.I)
        if m:
            result["founded"] = m.group(1)

    # ── Log the fetch operation ────────────────────────────────────────────────
    append_log("fetch", company_name, "fetch_company_info")

    # ── Fill N/A for unresolved fields ─────────────────────────────────────────
    for key in result:
        if result[key] is None or result[key] == "":
            result[key] = "N/A"

    return result


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 2 — File CRUD
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def company_file_crud(
    operation: str, company_name: str = "all", data: dict = None
) -> dict:
    """CRUD operations on local companies.json. Operations: create/read/update/delete/list."""
    if data is None:
        data = {}

    companies = load_companies()

    if operation == "create":
        if company_name in companies:
            append_log("create_fail", company_name, "company_file_crud")
            return {
                "status": "error",
                "message": f"Company '{company_name}' already exists. Use 'update' to modify.",
            }
        entry = {**data, "created_at": datetime.now(timezone.utc).isoformat()}
        companies[company_name] = entry
        save_companies(companies)
        append_log("create", company_name, "company_file_crud")
        return {"status": "success", "message": f"Created '{company_name}'", "data": entry}

    elif operation == "read":
        if company_name == "all":
            append_log("read", "all", "company_file_crud")
            return {"status": "success", "data": companies}
        if company_name not in companies:
            return {"status": "error", "message": f"Company '{company_name}' not found."}
        append_log("read", company_name, "company_file_crud")
        return {"status": "success", "data": companies[company_name]}

    elif operation == "update":
        if company_name not in companies:
            return {
                "status": "error",
                "message": f"Company '{company_name}' not found. Use 'create' first.",
            }
        companies[company_name].update(data)
        companies[company_name]["updated_at"] = datetime.now(timezone.utc).isoformat()
        save_companies(companies)
        append_log("update", company_name, "company_file_crud")
        return {
            "status": "success",
            "message": f"Updated '{company_name}'",
            "data": companies[company_name],
        }

    elif operation == "delete":
        if company_name not in companies:
            return {"status": "error", "message": f"Company '{company_name}' not found."}
        del companies[company_name]
        save_companies(companies)
        append_log("delete", company_name, "company_file_crud")
        return {"status": "success", "message": f"Deleted '{company_name}'"}

    elif operation == "list":
        append_log("list", "all", "company_file_crud")
        return {
            "status": "success",
            "companies": list(companies.keys()),
            "count": len(companies),
        }

    else:
        return {
            "status": "error",
            "message": f"Unknown operation '{operation}'. Valid: create/read/update/delete/list",
        }


# ─────────────────────────────────────────────────────────────────────────────
# TOOL 3 — Prefab UI Dashboard
# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def show_on_dashboard(companies_data: list = None, mode: str = "single") -> dict:
    """Generate and serve a live Prefab UI dashboard for all company data."""
    all_companies = load_companies()

    # Ensure "company" key is present in every entry
    for name, company in all_companies.items():
        if "company" not in company or not company["company"]:
            company["company"] = name

    companies_list = list(all_companies.values())
    logs = load_logs()

    # Auto-detect mode
    if len(companies_list) > 1:
        mode = "comparison"

    generated_code = _generate_prefab_code(companies_list, logs, mode)

    # ── Validate with py_compile ───────────────────────────────────────────────
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as tmp:
            tmp.write(generated_code)
            tmp_path = tmp.name
        py_compile.compile(tmp_path, doraise=True)
        os.unlink(tmp_path)
    except py_compile.PyCompileError as e:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass
        error_msg = f"Generated code is invalid Python: {e}"
        print(f"[MCP] {error_msg}", file=sys.stderr)
        return {"status": "error", "message": error_msg}

    # ── Write generated app (always overwrite) ─────────────────────────────────
    GENERATED_APP.write_text(generated_code, encoding="utf-8")
    print(f"[MCP] Wrote {GENERATED_APP}", file=sys.stderr)

    # ── Kill existing prefab serve process ─────────────────────────────────────
    if PID_FILE.exists():
        try:
            old_pid = PID_FILE.read_text().strip()
            if old_pid:
                subprocess.run(["kill", "-9", old_pid], capture_output=True)
                print(f"[MCP] Killed old prefab process PID={old_pid}", file=sys.stderr)
        except Exception as kill_err:
            print(f"[MCP] Could not kill old prefab process: {kill_err}", file=sys.stderr)
        PID_FILE.unlink(missing_ok=True)

    subprocess.run(["pkill", "-f", "prefab serve"], capture_output=True)
    time.sleep(1)

    # ── Resolve how to launch prefab serve ────────────────────────────────────
    # Strategy 1: direct binary in PATH
    prefab_bin = shutil.which("prefab")
    # Strategy 2: next to current Python interpreter (venv)
    if not prefab_bin:
        candidate = Path(sys.executable).parent / "prefab"
        if candidate.exists():
            prefab_bin = str(candidate)
    # Strategy 3: via uv tool run (handles uv-managed installs like on this machine)
    uv_bin = shutil.which("uv") or "/opt/homebrew/bin/uv"
    use_uv = not prefab_bin and Path(uv_bin).exists()

    # ── Start fresh prefab serve ───────────────────────────────────────────────
    try:
        with open(PREFAB_LOG, "w") as log_fh:
            if use_uv:
                cmd = [uv_bin, "tool", "run", "--from", "prefab-ui", "prefab",
                       "serve", GENERATED_APP.name, "--port", "5175"]
                print(f"[MCP] Launching via uv: {' '.join(cmd)}", file=sys.stderr)
            elif prefab_bin:
                cmd = [prefab_bin, "serve", GENERATED_APP.name, "--port", "5175"]
                print(f"[MCP] Launching prefab binary: {prefab_bin}", file=sys.stderr)
            else:
                return {"status": "error", "message": "prefab not found. Run: pip install prefab-ui"}
            proc = subprocess.Popen(
                cmd,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                cwd=str(BASE_DIR),
            )
        PID_FILE.write_text(str(proc.pid))
        append_log("dashboard", "all", "show_on_dashboard")
        print(f"[MCP] Prefab serve PID={proc.pid} — {len(companies_list)} companies", file=sys.stderr)
        return {
            "status": "success",
            "message": f"Dashboard live with {len(companies_list)} companies in {mode} mode.",
            "url": "http://127.0.0.1:5175",
            "companies_count": len(companies_list),
            "mode": mode,
        }
    except Exception as e:
        return {"status": "error", "message": f"Failed to start prefab serve: {e}"}


# ─────────────────────────────────────────────────────────────────────────────
# Code Generator
# ─────────────────────────────────────────────────────────────────────────────
def _generate_prefab_code(companies: list, logs: list, mode: str) -> str:
    """Return a complete, syntactically-valid Prefab UI Python script as a string."""

    # Encode data as base64-wrapped JSON to avoid any escaping issues
    companies_b64 = base64.b64encode(
        json.dumps(companies, default=str, ensure_ascii=False).encode("utf-8")
    ).decode()
    logs_b64 = base64.b64encode(
        json.dumps(logs, default=str, ensure_ascii=False).encode("utf-8")
    ).decode()

    # ── Derive chart data at generation time (pure Python, safe) ──────────────
    industry_counts: dict = {}
    for c in companies:
        ind = str(c.get("industry") or "Unknown").strip() or "Unknown"
        if ind == "N/A":
            ind = "Unknown"
        industry_counts[ind] = industry_counts.get(ind, 0) + 1

    pie_data_repr = repr([{"name": k, "value": v} for k, v in industry_counts.items()])

    _tracked = ["description", "summary", "founded", "key_people", "industry"]
    def _pct(c):
        filled = sum(1 for f in _tracked if c.get(f) and str(c[f]).strip() not in ("N/A", "None", "", "Unknown"))
        return int(filled / len(_tracked) * 100)

    current_year = datetime.now(timezone.utc).year
    bar_data = []
    fin_data_dict = {}
    for c in companies:
        founded_raw = str(c.get("founded") or "")
        m = re.search(r"\b(1[5-9]\d{2}|20\d{2})\b", founded_raw)
        year = int(m.group(1)) if m else 0
        age = current_year - year if year else 0

        cagr_raw = c.get("cagr_5yr_pct")
        try:
            cagr_val = float(cagr_raw) if cagr_raw not in (None, "N/A", "None", "nan", "") else 0.0
        except (ValueError, TypeError):
            cagr_val = 0.0

        sp_raw = str(c.get("share_price") or "")
        try:
            sp_num = float(sp_raw.split()[0]) if sp_raw and sp_raw not in ("N/A", "N/A (unlisted)") else 0.0
        except (ValueError, IndexError):
            sp_num = 0.0

        cname = str(c.get("company", "?"))
        bar_data.append({
            "company": cname[:16],
            "age_years": age,
            "completeness_pct": _pct(c),
            "cagr_5yr_pct": round(cagr_val, 1),
            "share_price_num": round(sp_num, 0),
        })
        fin_data_dict[cname] = {
            "ticker":       str(c.get("ticker", "N/A")),
            "share_price":  str(c.get("share_price", "N/A")),
            "cagr_5yr_pct": cagr_raw if cagr_raw not in (None, "N/A", "None", "nan", "") else None,
            "market_cap":   str(c.get("market_cap", "N/A")),
        }
    bar_data_repr = repr(bar_data)
    fin_data_repr = repr(fin_data_dict)

    date_counter: Counter = Counter()
    for c in companies:
        ts = str(c.get("fetched_at") or c.get("created_at") or "")
        if len(ts) >= 10:
            date_counter[ts[:10]] += 1
    sparkline_repr = repr(list(date_counter.values()) if date_counter else [0])

    total_companies = len(companies)
    total_ops = len(logs)
    last_updated = (
        logs[-1]["timestamp"][:19].replace("T", " ") if logs else "Never"
    )
    generated_at = datetime.now(timezone.utc).isoformat()

    # ── Template ───────────────────────────────────────────────────────────────
    code = f'''#!/usr/bin/env python3
"""
Company Intelligence Dashboard
Auto-generated by show_on_dashboard tool at {generated_at}
DO NOT edit this file manually — it is regenerated on every dashboard call.
"""

import json
import base64

from prefab_ui.app import PrefabApp
from prefab_ui.components import (
    Badge, Card, CardContent, CardHeader, CardTitle,
    Column, H1, H3, Muted, Progress, Row,
    Tab, Tabs, Text, Input, Button,
)
from prefab_ui.components.charts import BarChart, ChartSeries, PieChart, Sparkline

# ── Embedded data ──────────────────────────────────────────────────────────────
COMPANIES = json.loads(base64.b64decode("{companies_b64}").decode("utf-8"))
AGENT_LOG = json.loads(base64.b64decode("{logs_b64}").decode("utf-8"))

PIE_DATA = {pie_data_repr}
BAR_DATA = {bar_data_repr}
FINANCIAL_DATA = {fin_data_repr}
SPARKLINE_DATA = {sparkline_repr}

TOTAL_COMPANIES = {total_companies}
TOTAL_OPS = {total_ops}
LAST_UPDATED = {repr(last_updated)}
MODE = {repr(mode)}
GENERATED_AT = {repr(generated_at)}


# ── Helpers ────────────────────────────────────────────────────────────────────
_TRACKED_FIELDS = ["description", "summary", "founded", "key_people", "industry"]

def _completeness(company: dict) -> int:
    filled = sum(
        1 for f in _TRACKED_FIELDS
        if company.get(f) and str(company[f]).strip() not in ("N/A", "None", "", "Unknown")
    )
    return int(filled / len(_TRACKED_FIELDS) * 100)

def _variant_for_pct(pct: int) -> str:
    if pct >= 80: return "success"
    if pct >= 50: return "warning"
    return "destructive"

def _variant_for_cagr(cagr) -> str:
    if cagr is None: return "secondary"
    try:
        v = float(cagr)
        if v >= 15: return "success"
        if v >= 5: return "warning"
        return "destructive"
    except (ValueError, TypeError):
        return "secondary"

def _count_people(key_people: str) -> int:
    if not key_people or key_people in ("N/A", "None", ""):
        return 0
    return len([p.strip() for p in key_people.split(",") if p.strip()])

def _fin(company_name: str) -> dict:
    return FINANCIAL_DATA.get(company_name, {{}})


# ── Tab builders ───────────────────────────────────────────────────────────────
def build_overview_tab():
    if not COMPANIES:
        return Column(children=[
            H3("No companies loaded yet."),
            Muted("Run the agent with a company name to populate this dashboard."),
        ])

    cards = []
    for c in COMPANIES:
        pct       = _completeness(c)
        name      = str(c.get("company", "Unknown"))
        desc      = str(c.get("description", ""))
        summary   = str(c.get("summary", ""))
        industry  = str(c.get("industry", "N/A"))
        founded   = str(c.get("founded", "N/A"))
        key_people = str(c.get("key_people", "N/A"))
        source    = str(c.get("source_url", ""))
        fin       = _fin(name)

        summary_short = summary[:280] + "…" if len(summary) > 280 else summary
        kp_short = key_people[:100] + "…" if len(key_people) > 100 else key_people
        variant = _variant_for_pct(pct)

        sp    = fin.get("share_price", "N/A")
        cagr  = fin.get("cagr_5yr_pct")
        mc    = fin.get("market_cap", "N/A")
        cagr_label = f"{{cagr}}% / yr" if cagr is not None else "N/A"
        cagr_variant = _variant_for_cagr(cagr)

        cards.append(
            Card(children=[
                CardHeader(children=[
                    Row(children=[
                        CardTitle(name),
                        Badge(f"{{pct}}% data quality", variant=variant),
                    ]),
                    Muted(desc) if desc and desc not in ("N/A", "") else Muted(""),
                ]),
                CardContent(children=[
                    Text(summary_short) if summary_short and summary_short != "N/A" else Text(""),
                    Row(children=[
                        Column(children=[Muted("Founded"), Text(founded)]),
                        Column(children=[Muted("Industry"), Text(industry)]),
                        Column(children=[Muted("Share Price"), Text(sp)]),
                    ]),
                    Row(children=[
                        Column(children=[Muted("5yr CAGR"), Badge(cagr_label, variant=cagr_variant)]),
                        Column(children=[Muted("Market Cap"), Text(mc)]),
                    ]),
                    Muted(f"Key People: {{kp_short}}") if key_people not in ("N/A", "") else Muted(""),
                    Progress(value=pct, variant=variant),
                    Muted(f"Data quality: {{pct}}%  ·  Source: {{source[:50]}}") if source else Muted(f"Data quality: {{pct}}%"),
                ]),
            ])
        )

    return Column(children=[
        H1("Company Overview"),
        Muted(f"{{TOTAL_COMPANIES}} companies tracked  ·  Last updated {{LAST_UPDATED}}"),
        *cards,
    ])


def build_comparison_tab():
    if len(COMPANIES) <= 1:
        return Column(children=[
            Muted("Add at least 2 companies to enable comparison view."),
        ])

    cagr_chart = BarChart(
        data=BAR_DATA,
        series=[ChartSeries(data_key="cagr_5yr_pct", label="5-Year CAGR (%)")],
        x_axis="company",
        height=260,
    )

    price_chart = BarChart(
        data=BAR_DATA,
        series=[ChartSeries(data_key="share_price_num", label="Share Price (local currency)")],
        x_axis="company",
        height=260,
    )

    age_chart = BarChart(
        data=BAR_DATA,
        series=[ChartSeries(data_key="age_years", label="Company Age (years)")],
        x_axis="company",
        height=220,
    )

    header_row = Row(children=[
        Badge("Company",     variant="secondary"),
        Badge("Industry",    variant="secondary"),
        Badge("Founded",     variant="secondary"),
        Badge("Share Price", variant="secondary"),
        Badge("5yr CAGR",    variant="secondary"),
        Badge("Market Cap",  variant="secondary"),
    ])

    data_rows = []
    for c in COMPANIES:
        name = str(c.get("company", "N/A"))
        fin  = _fin(name)
        sp   = str(fin.get("share_price", "N/A"))
        cagr = fin.get("cagr_5yr_pct")
        mc   = str(fin.get("market_cap", "N/A"))
        cagr_label = f"{{cagr}}%" if cagr is not None else "N/A"
        data_rows.append(Row(children=[
            Text(name[:18]),
            Text(str(c.get("industry", "N/A"))[:20]),
            Text(str(c.get("founded", "N/A"))[:12]),
            Text(sp),
            Badge(cagr_label, variant=_variant_for_cagr(cagr)),
            Text(mc),
        ]))

    return Column(children=[
        H1("Side-by-Side Comparison"),
        H3("5-Year CAGR (%)"),
        Muted("Compound Annual Growth Rate based on stock price over 5 years  ·  Private companies show 0"),
        cagr_chart,
        H3("Current Share Price"),
        Muted("Latest market price in local currency  ·  0 = unlisted / private"),
        price_chart,
        H3("Company Age (Years Since Founding)"),
        Muted("Track record depth — older companies have more historical performance data"),
        age_chart,
        H3("Full Comparison Table"),
        header_row,
        *data_rows,
    ])


def build_search_tab():
    return Column(children=[
        H1("Search & Add"),
        Muted("Use the agent to fetch and save new companies — the dashboard refreshes automatically."),
        H3("Add a New Company"),
        Row(children=[
            Input(placeholder="Enter company name…"),
            Button("Fetch & Add"),
        ]),
        Muted("After entering a name, run:  python agent.py  in your terminal."),
        H3("Daily Additions"),
        Sparkline(data=SPARKLINE_DATA),
    ])


def build_log_tab():
    _OP_VARIANT = {{
        "fetch":       "secondary",
        "create":      "success",
        "create_fail": "destructive",
        "read":        "default",
        "update":      "warning",
        "delete":      "destructive",
        "list":        "secondary",
        "dashboard":   "secondary",
    }}
    _OP_ICON = {{
        "fetch":       "FETCH",
        "create":      "ADD",
        "create_fail": "SKIP",
        "read":        "READ",
        "update":      "UPDATE",
        "delete":      "DEL",
        "list":        "LIST",
        "dashboard":   "UI",
    }}

    if not AGENT_LOG:
        return Column(children=[
            H1("Agent Activity Log"),
            Muted("No activity logged yet."),
        ])

    log_cards = []
    for entry in reversed(AGENT_LOG):
        op      = str(entry.get("operation", "unknown"))
        company = str(entry.get("company", "?"))
        tool    = str(entry.get("tool", "unknown_tool"))
        ts_raw  = str(entry.get("timestamp", ""))
        ts_date = ts_raw[:10] if ts_raw else "?"
        ts_time = ts_raw[11:19] if len(ts_raw) >= 19 else "?"
        variant = _OP_VARIANT.get(op, "default")
        icon    = _OP_ICON.get(op, op.upper())

        log_cards.append(
            Card(children=[
                CardContent(children=[
                    Row(children=[
                        Badge(icon, variant=variant),
                        Column(children=[
                            Row(children=[
                                Text(company),
                                Badge(tool, variant="secondary"),
                            ]),
                            Muted(f"{{ts_date}}  {{ts_time}} UTC"),
                        ]),
                    ]),
                ]),
            ])
        )

    op_counts: dict = {{}}
    for entry in AGENT_LOG:
        op = str(entry.get("operation", "unknown"))
        op_counts[op] = op_counts.get(op, 0) + 1
    summary_badges = [
        Badge(f"{{op.upper()}} x{{cnt}}", variant=_OP_VARIANT.get(op, "default"))
        for op, cnt in op_counts.items()
    ]

    return Column(children=[
        H1("Agent Activity Log"),
        Muted(f"{{TOTAL_OPS}} operations total  ·  Last: {{LAST_UPDATED}}"),
        Row(children=summary_badges),
        *log_cards,
    ])


def build_stats_tab():
    op_counts: dict = {{}}
    for entry in AGENT_LOG:
        op = str(entry.get("operation", "unknown"))
        op_counts[op] = op_counts.get(op, 0) + 1

    _OP_VARIANT = {{
        "create": "success",
        "update": "warning",
        "delete": "destructive",
        "read": "default",
        "list": "secondary",
        "dashboard": "secondary",
    }}

    company_activity: dict = {{}}
    for entry in AGENT_LOG:
        co = str(entry.get("company", "?"))
        if co != "all":
            company_activity[co] = company_activity.get(co, 0) + 1
    most_active = max(company_activity, key=lambda k: company_activity[k]) if company_activity else "N/A"

    completeness_vals = [_completeness(c) for c in COMPANIES]
    avg_completeness = int(sum(completeness_vals) / len(completeness_vals)) if completeness_vals else 0

    pie = PieChart(
        data=PIE_DATA if PIE_DATA else [{{"name": "No Data", "value": 1}}],
        data_key="value",
        name_key="name",
    )

    op_badge_row = [
        Badge(f"{{op.upper()}}: {{cnt}}", variant=_OP_VARIANT.get(op, "default"))
        for op, cnt in op_counts.items()
    ]

    best_cagr_company = "N/A"
    best_cagr_val = None
    for c in COMPANIES:
        cname = str(c.get("company", ""))
        cagr_c = _fin(cname).get("cagr_5yr_pct")
        if cagr_c is not None:
            try:
                cf = float(cagr_c)
                if best_cagr_val is None or cf > best_cagr_val:
                    best_cagr_val = cf
                    best_cagr_company = f"{{cname[:12]}} ({{cf}}%)"
            except (ValueError, TypeError):
                pass

    quality_rows = []
    for c in COMPANIES:
        pct      = _completeness(c)
        name     = str(c.get("company", "?"))
        industry = str(c.get("industry", "N/A"))
        n_people = _count_people(str(c.get("key_people", "")))
        fin      = _fin(name)
        cagr     = fin.get("cagr_5yr_pct")
        sp       = str(fin.get("share_price", "N/A"))
        variant  = _variant_for_pct(pct)
        cagr_label = f"CAGR {{cagr}}%" if cagr is not None else "CAGR N/A"
        quality_rows.append(Column(children=[
            Row(children=[
                Text(name),
                Badge(f"{{pct}}% quality", variant=variant),
                Badge(cagr_label, variant=_variant_for_cagr(cagr)),
                Badge(sp[:16], variant="default"),
                Badge(f"{{n_people}} leaders", variant="secondary") if n_people else Badge("leaders N/A", variant="secondary"),
                Badge(industry[:18] if industry != "N/A" else "sector N/A", variant="default"),
            ]),
            Progress(value=pct, variant=variant),
        ]))

    return Column(children=[
        H1("Stats & Metrics"),
        Row(children=[
            Card(children=[CardContent(children=[
                Muted("Companies Tracked"),
                H3(str(TOTAL_COMPANIES)),
            ])]),
            Card(children=[CardContent(children=[
                Muted("Avg. Data Quality"),
                H3(f"{{avg_completeness}}%"),
            ])]),
            Card(children=[CardContent(children=[
                Muted("Total Agent Ops"),
                H3(str(TOTAL_OPS)),
            ])]),
            Card(children=[CardContent(children=[
                Muted("Most Active"),
                H3(most_active[:16]),
            ])]),
            Card(children=[CardContent(children=[
                Muted("Best 5yr CAGR"),
                H3(best_cagr_company[:18]),
            ])]),
        ]),
        H3("Operations Breakdown"),
        Muted("Count of each operation type performed by the agent"),
        Row(children=op_badge_row) if op_badge_row else Muted("No operations yet."),
        H3("Industry Distribution"),
        pie,
        H3("Company Intelligence Scores"),
        Muted("Data quality · Leadership coverage · Industry classification per company"),
        *quality_rows,
        Muted(f"Generated at: {{GENERATED_AT}}"),
    ])


# ── App assembly ───────────────────────────────────────────────────────────────
app = PrefabApp(title="Company Intelligence Dashboard")

app.view = Tabs(children=[
    Tab("Overview",     children=[build_overview_tab()]),
    Tab("Comparison",   children=[build_comparison_tab()]),
    Tab("Search & Add", children=[build_search_tab()]),
    Tab("Agent Log",    children=[build_log_tab()]),
    Tab("Stats",        children=[build_stats_tab()]),
])
'''

    return code


# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("✓ MCP Server running — 3 tools registered", file=sys.stderr)
    print("  → SSE endpoint: http://127.0.0.1:8000/sse", file=sys.stderr)
    mcp.run(transport="sse", host="127.0.0.1", port=8000)
