# Voiceover Script — Company Intelligence Agent (EAGv3 Session 4)

> **Instructions for AI voiceover:** Read naturally, pause at `[PAUSE]` markers.
> Sections marked `[SCREEN]` indicate what should be visible on screen at that point.
> Total estimated runtime: ~5–7 minutes.

---

## INTRO

[SCREEN: Project folder / terminal open]

Hi everyone. In this video I'm going to walk you through what I built for Session 4 of EAGv3 — a fully working **Company Intelligence Agent** powered by the **Model Context Protocol**, or MCP.

This is not just a chatbot. This is a real AI agent that can search the web, save data to a local database, and render a live interactive dashboard — all through a structured protocol that any AI model can speak.

Let's get into it.

[PAUSE]

---

## WHAT IS MCP?

[SCREEN: Architecture diagram from README]

MCP stands for the **Model Context Protocol**. Think of it like a USB standard — but for AI tools.

Before MCP, every developer had to figure out their own way to connect an AI model to external tools. JSON schemas, custom wrappers, glue code everywhere. It was messy.

MCP solves this by defining a standard way for AI models to discover and call tools. The model asks: "what tools do you have?" The server responds with a list. The model picks one, sends arguments, gets back a result. Clean, composable, reusable.

In my project, the MCP server runs as a separate process and exposes **three tools**. The agent is the client — it connects over Server-Sent Events, discovers the tools, and uses them in a loop to complete the task.

[PAUSE]

---

## THE THREE TOOLS

[SCREEN: mcp_server.py open, scroll through tool definitions]

Let me show you the three tools I built inside `mcp_server.py`.

**Tool 1: `fetch_company_info`**

This tool takes a company name and goes out to the web — Wikipedia and DuckDuckGo — to fetch structured information. It returns a dictionary with the company's description, summary, founding year, key people, industry, and the source URL. Real web data, not made-up stuff.

[PAUSE]

**Tool 2: `company_file_crud`**

This is the persistence layer. It supports create, read, update, delete, and list operations on a local JSON file — `data/companies.json`. Every write is done atomically: data is written to a temporary file first, then renamed, so you can never end up with a corrupted database even if something crashes mid-write.

Every operation also gets logged to `data/agent_log.json` with the company name, the tool used, and a UTC timestamp. That log powers the Agent Log tab on the dashboard.

[PAUSE]

**Tool 3: `show_on_dashboard`**

This is the most interesting one. When called, it reads the current state of the companies database and the activity log, encodes them as base64, and generates a complete Python file called `generated_app.py` — a fully self-contained Prefab UI application.

It then launches that file using `uv tool run prefab serve`, which starts a local web server on port 5175. Your browser can open it immediately.

The entire dashboard — cards, charts, logs, comparisons — is generated fresh every time this tool is called. No stale data.

[PAUSE]

---

## THE AGENT

[SCREEN: agent.py open]

Now let me show you the agent — `agent.py`.

The agent uses **Gemini 2.0 Flash** as its brain. I'm using Google's `google-genai` SDK for this.

The agent runs a **ReAct loop** — that stands for Reasoning and Acting. Each iteration looks like this:

1. The agent sends the conversation history (including all previous tool calls and results) to Gemini.
2. Gemini either responds with text — meaning it's done — or it responds with one or more **function calls**.
3. The agent executes those function calls against the MCP server.
4. The results are appended to the conversation history.
5. Repeat.

This continues for up to 15 iterations, which is enough to handle even complex multi-company tasks.

[PAUSE]

One thing worth noting: I built in **automatic retry logic**. If the Gemini API returns a 429 — which means rate limit exceeded — or a 503 service unavailable, the agent waits and retries up to three times. This makes it robust against temporary API issues.

[PAUSE]

---

## TWO WORKFLOWS

[SCREEN: SYSTEM_PROMPT section in agent.py]

The agent supports two distinct workflows, controlled by how you phrase your prompt.

**Workflow A — Web Fetch Mode (default)**

If your prompt says "fetch" or doesn't specify otherwise, the agent will:
- Call `fetch_company_info` for each company to get real web data
- Enrich that data with its own knowledge — share price, ticker symbol, 5-year CAGR, market cap
- Save everything with `company_file_crud`
- Launch the dashboard

**Workflow B — LLM Knowledge Mode**

If your prompt says "use LLM knowledge", "no fetch", or "skip fetch", the agent skips the web search entirely. It builds the full company data dictionary from its training knowledge and goes straight to saving and displaying.

This is useful when you want speed, or when you're adding a company that might not have great Wikipedia coverage.

[PAUSE]

---

## THE DASHBOARD

[SCREEN: Browser open at http://127.0.0.1:5175]

Let's look at the dashboard. This was generated by the `show_on_dashboard` tool using the **Prefab UI** framework.

It has five tabs:

**Overview** — shows each company as a card. You can see the industry badge, founding year, key people, and a ring that visually represents how complete the data is. The more fields filled in, the more of the ring is colored.

**Comparison** — a bar chart comparing companies by their founding year, plus a side-by-side grid of all their data fields. Great for spotting differences at a glance.

**Search & Add** — a UI for adding companies by name, with a sparkline chart showing how many companies were added each day.

**Agent Log** — every single operation the agent has performed, with the company name, a color-coded badge showing which tool was called, and the exact timestamp. Nothing is hidden, nothing is capped.

**Stats** — a pie chart breaking down companies by industry, progress bars for data completeness, and summary badges at the bottom.

[PAUSE]

---

## LIVE DEMO

[SCREEN: Terminal 1 — run mcp_server.py]

Let me show you the full flow live.

First, I start the MCP server in Terminal 1.

```
python mcp_server.py
```

You can see it registers the three tools and starts listening on port 8000 over SSE.

[SCREEN: Terminal 2 — run agent.py]

Now in Terminal 2, I run the agent with a prompt to fetch and display company information.

```
python agent.py
```

Watch the iteration-by-iteration output. Each `[TOOL CALL]` line shows the agent deciding to use a tool. Each `[TOOL RESULT]` shows what it got back. The agent reasons about those results and decides what to do next.

[SCREEN: Browser refreshing dashboard]

After the final tool call — `show_on_dashboard` — the dashboard refreshes with the new data. All the companies appear, the log updates, the charts render.

[PAUSE]

---

## WHAT I LEARNED

[SCREEN: File tree of the project]

This project taught me a few important things.

**MCP separates concerns cleanly.** The agent doesn't know how web scraping works. The dashboard doesn't know about the agent. Each tool is independently testable. That's good software design.

**ReAct loops are powerful but need guardrails.** Without the 15-iteration cap, an agent can get into loops or spend too much time on a single task. The cap forces efficiency.

**Runtime data doesn't belong in git.** The `.gitignore` I set up keeps `companies.json`, `agent_log.json`, `generated_app.py`, and `prefab.pid` out of the repository. These are all created fresh at runtime — committing them would just create noise.

**Protocol matters more than implementation.** Because the agent speaks MCP, I could swap Gemini for Claude or GPT-4 tomorrow and the tools would still work unchanged. That's the real power here.

[PAUSE]

---

## WRAP UP

[SCREEN: README.md]

To summarize — I built a Company Intelligence Agent that:

- Uses MCP as the tool protocol between the AI brain and the tool implementations
- Fetches real web data or uses LLM knowledge, depending on the prompt
- Persists company data and activity logs locally
- Generates a fully interactive Prefab dashboard on demand
- Handles API rate limits gracefully with automatic retry

All the code is in this repository. The README has setup instructions, the architecture diagram, and all the commands you need to run it yourself.

Thanks for watching.

[PAUSE]

---

*Script end. Total estimated runtime at natural reading pace: ~6 minutes.*
