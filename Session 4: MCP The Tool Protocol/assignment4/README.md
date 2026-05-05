# Company Intelligence Agent — EAGv3 Session 4

A multi-tool AI agent that fetches company data from the web, persists it locally,
and displays it on a live Prefab UI dashboard — all orchestrated via the
**Model Context Protocol (MCP)**.

---

## Demo Video

> **YouTube:** _(link coming soon — will be updated)_

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                      USER PROMPT                             │
│             (terminal input → agent.py)                      │
└─────────────────────────┬────────────────────────────────────┘
                          │  ReAct loop (Gemini 2.0 Flash)
                          ▼
┌──────────────────────────────────────────────────────────────┐
│                    agent.py                                  │
│   • Gemini 2.0 Flash (google-genai)                          │
│   • FastMCP Client → connects to MCP server via SSE          │
│   • Max 15 tool-call iterations                              │
└────────┬─────────────────────────────────────────────────────┘
         │ MCP / SSE (port 8000)
         ▼
┌─────────────────────┐
│   mcp_server.py     │
│                     │              ┌──────────────────────────┐
│  Tool 1             │              │  show_on_dashboard       │
│  fetch_company_info │              │  → generated_app.py      │
│  (Wikipedia + DDG)  │              │  → prefab serve :5175    │
│                     │              └──────────────────────────┘
│  Tool 2             │              ┌──────────────────────────┐
│  company_file_crud  │◄────────────►│  data/companies.json     │
│  (CRUD on JSON)     │              │  data/agent_log.json     │
│                     │              └──────────────────────────┘
│  Tool 3             │
│  show_on_dashboard  │
│  (Prefab UI gen)    │
└─────────────────────┘
```

---

## Setup

### 1 — Navigate to this folder

```bash
cd "Session 4: MCP The Tool Protocol/assignment4"
```

### 2 — Install dependencies

```bash
pip install -r requirements.txt
```

### 3 — Configure environment variables

Edit `.env` (already in this folder — **never commit it**):

```
GEMINI_API_KEY=your_gemini_api_key_here
```

---

## How to Run

Open **two separate terminals** in the `assignment4/` directory:

**Terminal 1 — MCP Server:**
```bash
python mcp_server.py
```
Expected output: `✓ MCP Server running — 3 tools registered`

**Terminal 2 — Agent:**
```bash
python agent.py
```
Press Enter to use the built-in demo prompt, or pass your own:
```bash
python agent.py "Fetch info about Apple and Microsoft. Save them and show the dashboard."
```

**Browser — Dashboard** (auto-launched after agent calls `show_on_dashboard`):
```
http://127.0.0.1:5175
```

---

## Agent Workflows

**Workflow A — Web fetch (default):**
When the prompt says "fetch" or doesn't mention "LLM knowledge":
1. `fetch_company_info` for each company (Wikipedia + DuckDuckGo)
2. Enrich with financial data from Gemini's own knowledge
3. `company_file_crud` to persist
4. `show_on_dashboard` once at the end

**Workflow B — LLM knowledge only:**
When the prompt says "use LLM knowledge", "no fetch", or "skip fetch":
1. Skip `fetch_company_info` entirely
2. Gemini builds the full data dict from its training knowledge
3. `company_file_crud` to persist
4. `show_on_dashboard` once at the end

---

## Demo Prompt

```
Fetch detailed information about Reliance Industries and Infosys from the web.
For each company, also include financial data: ticker symbol, approximate
current share price, 5-year CAGR (%), and market cap. Save each company to
the local data file. Then show both companies on the Prefab dashboard in
comparison mode.
```

**Expected tool call sequence (5 calls minimum):**
1. `fetch_company_info("Reliance Industries")`
2. `fetch_company_info("Infosys")`
3. `company_file_crud(operation="create", company_name="Reliance Industries", data={...})`
4. `company_file_crud(operation="create", company_name="Infosys", data={...})`
5. `show_on_dashboard(mode="comparison")`

---

## Sample Run Output

Below is a real run of the agent fetching **Tata Motors** and **Infosys**.

```
Enter prompt: detailed information about tatamotors and Infosys from the web.
For each company, also include financial data you know: ticker symbol,
approximate current share price, 5-year CAGR (%), and market cap.
Save each company to the local data file. Then show both companies
on the Prefab dashboard in comparison mode.

MCP Server: http://127.0.0.1:8000/sse
Model: gemini-2.0-flash  |  Max iterations: 15
Discovered 3 tools: ['fetch_company_info', 'company_file_crud', 'show_on_dashboard']
```

**Iteration 1 — Fetch both companies in parallel:**
```
[TOOL CALL] fetch_company_info  { "company_name": "Tata Motors" }
[TOOL RESULT] { "company": "Tata Motors", "description": "Indian multinational automobile
  manufacturing company", "summary": "Tata Motors Limited...", "founded": "September 1, 1945",
  "industry": "Automotive", "source_url": "https://en.wikipedia.org/wiki/Tata_Motors" }

[TOOL CALL] fetch_company_info  { "company_name": "Infosys" }
[TOOL RESULT] { "company": "Infosys", "description": "Indian multinational technology company",
  "summary": "Infosys Limited is an Indian multinational technology company...",
  "founded": "2 July 1981 in Pune, India", "key_people": "N. R. Narayana Murthy, Nandan
  Nilekani, Kris Gopalakrishnan...", "industry": "Information technology Consulting" }
```

**Iteration 2 — Save both companies (Infosys already existed → error):**
```
[TOOL CALL] company_file_crud  { "operation": "create", "company_name": "Tata Motors",
  "data": { "ticker": "TATAMOTORS.NS", "share_price": "950 INR",
             "cagr_5yr_pct": 25, "market_cap": "3.5T INR", ... } }
[TOOL RESULT] { "status": "success", "message": "Created 'Tata Motors'" }

[TOOL CALL] company_file_crud  { "operation": "create", "company_name": "Infosys", ... }
[TOOL RESULT] { "status": "error",
  "message": "Company 'Infosys' already exists. Use 'update' to modify." }
```

**Iteration 3 — Agent self-corrects, retries Infosys with update:**
```
[TOOL CALL] company_file_crud  { "operation": "update", "company_name": "Infosys",
  "data": { "ticker": "INFY.NS", "share_price": "1500 INR",
             "cagr_5yr_pct": 12, "market_cap": "6.5T INR", ... } }
[TOOL RESULT] { "status": "success", "message": "Updated 'Infosys'" }
```

**Iteration 4 — Launch the dashboard:**
```
[TOOL CALL] show_on_dashboard  { "mode": "comparison", "companies_data": [...] }
[TOOL RESULT] { "status": "success",
  "message": "Dashboard live with 4 companies in comparison mode.",
  "url": "http://127.0.0.1:5175" }
```

**Iteration 5 — Gemini sees success, returns final text:**
```
[GEMINI] I have successfully fetched, enriched, and saved the data for
Tata Motors and Infosys.

• Tata Motors: ticker TATAMOTORS.NS, share price 950 INR, 5yr CAGR 25%, market cap 3.5T INR
• Infosys:     ticker INFY.NS, share price 1500 INR, 5yr CAGR 12%, market cap 6.5T INR

The comparison dashboard is now live at http://127.0.0.1:5175

[AGENT] No more tool calls — task complete.
```

> The agent used **5 iterations** and **6 tool calls** total. It correctly self-corrected when
> Infosys already existed (auto-switched create → update without any user intervention).

---

## File Reference

| File | Purpose |
|------|---------|
| `mcp_server.py` | MCP server with 3 tools (SSE on port 8000) |
| `agent.py` | Gemini 2.0 Flash ReAct agent |
| `generated_app.py` | Auto-written by Tool 3 on every dashboard call |
| `data/companies.json` | Persisted company data (keyed by name) |
| `data/agent_log.json` | Every tool operation logged with timestamp |
| `prefab_server.log` | stdout/stderr from `prefab serve` |
| `.env` | API keys — **never commit** |
| `requirements.txt` | Python dependencies |

---

## Dashboard Tabs

| Tab | Content |
|-----|---------|
| **Overview** | Company cards with data-completeness ring, industry badges |
| **Comparison** | BarChart (founded year), side-by-side data grid |
| **Search & Add** | Input + Button UI, Sparkline of daily additions |
| **Agent Log** | All operations with color-coded tool badges and timestamps |
| **Stats** | PieChart by industry, progress bars, summary badges |

---

## Notes

- `data/` directory and JSON files are created automatically on first run.
- `generated_app.py` is validated with `py_compile` before writing — invalid code is rejected.
- The agent caps at 15 tool-call iterations to prevent infinite loops.
- All timestamps are ISO 8601 (UTC).
- `companies.json` is written atomically (tmp file → rename) to prevent corruption.
- The agent retries automatically on Gemini 429 / 503 errors (up to 3×).
