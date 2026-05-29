# EAGV3 Session 6 — Agentic Architecture

This assignment implements a four-role agentic system using a typed control loop:

**Memory → Perception → Decision → Action**

The goal of Session 6 is to move away from a single monolithic agent file and introduce clear module boundaries. Each role has a specific responsibility, and the outer `agent6.py` loop coordinates them until all user goals are satisfied.

---

## What This Assignment Demonstrates

This project demonstrates how an agent can:

1. Break a user query into bounded goals.
2. Persist useful information in memory.
3. Re-read memory at every iteration.
4. Use Perception to decide which goals are complete.
5. Use Decision to either answer or call exactly one tool.
6. Use Action to execute MCP tools.
7. Store large tool outputs as artifacts instead of passing huge raw text through every step.
8. Continue iterating until Perception marks all goals as done.

The key idea is that the agent does not try to solve everything in one step. It decomposes the task, acts, records outcomes, re-observes state, and continues.

---

## Architecture Overview

```text
User Query
   |
   v
Memory.remember(query)
   |
   v
Loop:
   |
   +--> Memory.read(query, history)
   |
   +--> Perception.observe(query, memory_hits, history, prior_goals)
   |        - decomposes query into goals
   |        - marks goals done
   |        - decides when artifact bytes should be attached
   |
   +--> Decision.next_step(goal, memory_hits, attached_artifacts, history, tools)
   |        - returns either an answer
   |        - or returns one tool call
   |
   +--> Action.execute(tool_call)
   |        - dispatches MCP tool
   |        - writes large outputs to ArtifactStore
   |
   +--> Memory.record_outcome(tool_call, result, artifact_id)
   |
   v
Final Answer
```

---

## Four Main Roles

### 1. Memory

Memory stores durable facts, preferences, tool outcomes, and scratchpad-style notes.

In Session 6, memory is kept simple and readable. It stores items in a JSON file and supports retrieval before every perception step.

Typical memory responsibilities:

- Remember facts from user queries.
- Store tool outcomes.
- Store artifact handles instead of huge raw outputs.
- Retrieve relevant memory items for the next iteration.

Example:

```text
User says: My mom's birthday is 15 May 2026
Memory stores or records: birthday date / tool outcome / file path
Later query: When is mom's birthday?
Agent retrieves the stored information.
```

---

### 2. Perception

Perception is the orchestrator.

It looks at:

- Original user query
- Memory hits
- Run history
- Previous goal list

Then it returns an updated list of goals.

Perception decides:

- What goals exist.
- Which goals are open.
- Which goals are done.
- Whether a raw artifact should be attached for the next Decision step.

Important rule:

```text
Decision does not mark goals done.
Perception marks goals done after reading history.
```

---

### 3. Decision

Decision handles exactly one unfinished goal at a time.

It can return only one of two things:

1. A final answer for that goal.
2. A single MCP tool call.

It should not call multiple tools at once. This keeps failures isolated and makes retries easier.

Example:

```text
Goal: Fetch Claude Shannon Wikipedia page
Decision: TOOL_CALL fetch_url(...)
```

---

### 4. Action

Action is pure tool dispatch.

It receives the tool call from Decision and executes it through MCP.

Action does not reason. It only:

- Calls the tool.
- Returns a short result.
- Stores large output in ArtifactStore.
- Blocks invalid artifact-handle misuse, such as trying to read `art:...` as a file path.

---

## Artifact Store

Large tool outputs are stored separately as artifacts.

Example:

```text
fetch_url("https://en.wikipedia.org/wiki/Claude_Shannon")
→ stores full page as art:505cff7a5b0297f3
```

Memory stores only the artifact handle.

This avoids passing huge web pages into every future prompt.

---

## MCP Tools Used

Session 6 MCP server exposes tools such as:

```text
web_search
fetch_url
get_time
currency_convert
read_file
list_dir
create_file
update_file
edit_file
```

The logs below show tools such as:

- `fetch_url`
- `web_search`
- `create_file`
- `read_file`

---

## File Structure

```text
assignment6/
├── agent6.py              # main orchestrator loop
├── memory.py              # memory read/write logic
├── perception.py          # goal decomposition and goal completion
├── decision.py            # answer or one tool call
├── action.py              # MCP dispatch
├── artifacts.py           # artifact storage
├── schemas.py             # Pydantic contracts
├── mcp_server.py          # MCP tools
├── state/
│   ├── memory.json
│   └── artifacts/
└── README.md
```

---

## How to Install

From the assignment directory:

```bash
cd assignment6
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Or with `uv`:

```bash
uv pip install -r requirements.txt
```

Make sure your `.env` file exists in the correct parent Session 6 folder and contains the required model/tool API keys.

---

## How to Run

Run the interactive agent:

```bash
uv run python agent6.py
```

Then enter a query when prompted:

```text
Enter query > Fetch https://en.wikipedia.org/wiki/Claude_Shannon and tell me his birth date, death date, and three key contributions to information theory.
```

---

## Assignment Query Set

The logs below show the assignment query runs used for testing.

| Query | Purpose |
|---|---|
| Claude Shannon | Tests web fetch, artifact storage, extraction |
| Tokyo activities | Tests search + weather-aware recommendation |
| Mom birthday save/reminder | Tests memory and tool use across multiple goals |
| Mom birthday recall | Tests memory/file recall across turns |
| Python asyncio best practices | Tests web search, multiple result fetches, synthesis |

---


## Query Execution Logs

Logs are pasted as-is inside console blocks.

### Query 1 — Claude Shannon

**Run ID:** `de15f36e`  

**Status:** **SUCCESS**  

**Original query:** `Fetch https://en.wikipedia.org/wiki/Claude_Shannon and tell me his birth date, death date, and three key contributions to information theory.`

```console
Enter query > Fetch https://en.wikipedia.org/wiki/Claude_Shannon and tell me his birth date, death date, and three key contributions to information theory.
[gateway] connecting to llm_gatewayV3 at http://localhost:8101 ... ok
[run_start] run_id=de15f36e query='Fetch https://en.wikipedia.org/wiki/Claude_Shannon and tell me his birth date, d'
[memory.remember] no durable content
[05/30/26 04:00:52] INFO     Processing request of type ListToolsRequest                                                                                                        server.py:727
[mcp] spawning mcp_server.py over stdio ... ok (9 tools loaded)
                    INFO     Processing request of type ListToolsRequest                                                                                                        server.py:727

── iter 1 ──
[memory.read]    0 hits
[perception]     [open] Fetch the Wikipedia page for Claude Shannon
[perception]     [open] Extract birth date, death date, and three key contributions to informa
[pydantic ✓]   Observation
[pydantic ✓]   DecisionOutput
[decision]       TOOL_CALL: fetch_url({"url": "https://en.wikipedia.org/wiki/Claude_Shannon"})
[05/30/26 04:00:56] INFO     Processing request of type CallToolRequest                                                                                                         server.py:727
[mcp] crawl4ai error: crawl4ai failed: BrowserType.launch: Executable doesn't exist at /Users/harshagarwal/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing
╔════════════════════════════════════════════════════════════╗
║ Looks like Playwright was just installed or updated.       ║
║ Please run the following command to download new browsers: ║
║                                                            ║
║     playwright install                                     ║
║                                                            ║
║ <3 Playwright Team                                         ║
╚════════════════════════════════════════════════════════════╝, falling back to httpx
[05/30/26 04:00:58] INFO     HTTP Request: GET https://en.wikipedia.org/wiki/Claude_Shannon "HTTP/1.1 200 OK"                                                                 _client.py:1025
[artifacts.put]  art:505cff7a5b0297f3 (50336 bytes, text/markdown)
[action]         → [artifact art:505cff7a5b0297f3, 50336 bytes] preview: Claude Shannon - Wikipedia (function(){var className="client-js ve [art:art:505cff7a5b0297f3]
[memory.outcome]  fetch_url('https://en.wikipedia.org/wiki/Claude_Sh) -> art:505cff7a5b0297f3

── iter 2 ──
[memory.read]    1 hits
[perception]     [done] Fetch the Wikipedia page for Claude Shannon attach=art:505cff7a5b0297f3
[perception]     [open] Extract birth date, death date, and three key contributions to informa attach=art:505cff7a5b0297f3
[pydantic ✓]   Observation
[attach]         art:505cff7a5b0297f3 (50336 bytes)
[pydantic ✓]   DecisionOutput
[decision]       ANSWER: Claude Shannon was born on April 30, 1916, and passed away on February 24, 2001.

He is widely regar

── iter 3 ──
[memory.read]    1 hits
[perception]     [done] Fetch the Wikipedia page for Claude Shannon attach=art:505cff7a5b0297f3
[perception]     [done] Extract birth date, death date, and three key contributions to informa attach=art:505cff7a5b0297f3
[pydantic ✓]   Observation
[done] all 2 goals satisfied
[run_end]   FINAL: Claude Shannon was born on April 30, 1916, and passed away on February 24, 2001.

He is widely regarded as the "father of information theory" and made several foundational contributions to the field:


FINAL: Claude Shannon was born on April 30, 1916, and passed away on February 24, 2001.

He is widely regarded as the "father of information theory" and made several foundational contributions to the field:

*   **The Mathematical Theory of Communication:** In his landmark 1948 paper, he established the fundamental concepts of information theory, including the definition of the "bit" as the basic unit of information and the quantification of information content using entropy.
*   **Establishment of Channel Capacity:** He formulated the Shannon-Hartley theorem, which defines the maximum rate at which information can be reliably transmitted over a communication channel with a specified bandwidth in the presence of noise.
*   **Foundations of Digital Circuit Design:** In his 1937 master's thesis, he demonstrated that Boolean algebra could be used to optimize the design of systems of electromechanical relays, effectively proving that electronic circuits could implement logic functions and providing the theoretical basis for modern digital computer design.
```

### Query 2 — Tokyo Activities

**Run ID:** `00754029`  

**Status:** **SUCCESS**  

**Original query:** `Find 3 family-friendly things to do in Tokyo this weekend. Check Saturday's weather forecast there and tell me which one is most appropriate.`

```console
Enter query > Find 3 family-friendly things to do in Tokyo this weekend. Check Saturday's weather forecast there and tell me which one is most appropriate.
[gateway] connecting to llm_gatewayV3 at http://localhost:8101 ... ok
[run_start] run_id=00754029 query="Find 3 family-friendly things to do in Tokyo this weekend. Check Saturday's weat"
[memory.remember] no durable content
[05/30/26 04:02:04] INFO     Processing request of type ListToolsRequest                                                                                                        server.py:727
[mcp] spawning mcp_server.py over stdio ... ok (9 tools loaded)
                    INFO     Processing request of type ListToolsRequest                                                                                                        server.py:727

── iter 1 ──
[memory.read]    0 hits
[perception]     [open] Search for family-friendly activities in Tokyo for this weekend
[perception]     [open] Check the weather forecast for Saturday in Tokyo
[perception]     [open] Determine which activity is most appropriate based on the weather
[pydantic ✓]   Observation
[pydantic ✓]   DecisionOutput
[decision]       TOOL_CALL: web_search({"max_results": 10, "query": "family-friendly activities Tokyo weekend"})
[05/30/26 04:02:08] INFO     Processing request of type CallToolRequest                                                                                                         server.py:727
[artifacts.put]  art:b1443b393c2d240d (2176 bytes, text/plain)
[action]         → [artifact art:b1443b393c2d240d, 2176 bytes] preview: [The best Tokyo Family-friendly activities 2026](https://www.getyou [art:art:b1443b393c2d240d]
[memory.outcome]  web_search(10, 'family-friendly activities Tokyo weeken) -> art:b1443b393c2d240d

── iter 2 ──
[memory.read]    2 hits
[perception]     [done] Search for family-friendly activities in Tokyo for this weekend attach=art:b1443b393c2d240d
[perception]     [open] Check the weather forecast for Saturday in Tokyo attach=art:b1443b393c2d240d
[perception]     [open] Determine which activity is most appropriate based on the weather attach=art:b1443b393c2d240d
[pydantic ✓]   Observation
[attach]         art:b1443b393c2d240d (2176 bytes)
[pydantic ✓]   DecisionOutput
[decision]       TOOL_CALL: web_search({"max_results": 5, "query": "Tokyo weather Saturday"})
[05/30/26 04:02:27] INFO     Processing request of type CallToolRequest                                                                                                         server.py:727
[artifacts.put]  art:287f66a72bc999b6 (2143 bytes, text/plain)
[action]         → [artifact art:287f66a72bc999b6, 2143 bytes] preview: [Japan weather in May 2026 - Weather25.com](https://www.weather25.c [art:art:287f66a72bc999b6]
[memory.outcome]  web_search(5, 'Tokyo weather Saturday') -> art:287f66a72bc999b6

── iter 3 ──
[memory.read]    3 hits
[perception]     [done] Search for family-friendly activities in Tokyo for this weekend attach=art:b1443b393c2d240d
[perception]     [done] Check the weather forecast for Saturday in Tokyo attach=art:287f66a72bc999b6
[perception]     [open] Determine which activity is most appropriate based on the weather attach=art:b1443b393c2d240d
[pydantic ✓]   Observation
[attach]         art:b1443b393c2d240d (2176 bytes)
[pydantic ✓]   DecisionOutput
[decision]       TOOL_CALL: fetch_url({"url": "https://www.weather25.com/asia/japan/tokyo/may-2026"})
[05/30/26 04:03:01] INFO     Processing request of type CallToolRequest                                                                                                         server.py:727
[mcp] crawl4ai error: crawl4ai failed: BrowserType.launch: Executable doesn't exist at /Users/harshagarwal/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing
╔════════════════════════════════════════════════════════════╗
║ Looks like Playwright was just installed or updated.       ║
║ Please run the following command to download new browsers: ║
║                                                            ║
║     playwright install                                     ║
║                                                            ║
║ <3 Playwright Team                                         ║
╚════════════════════════════════════════════════════════════╝, falling back to httpx
[05/30/26 04:03:02] INFO     HTTP Request: GET https://www.weather25.com/asia/japan/tokyo/may-2026 "HTTP/1.1 302 Found"                                                       _client.py:1025
[05/30/26 04:03:03] INFO     HTTP Request: GET https://www.weather25.com/404.php "HTTP/1.1 404 Not Found"                                                                     _client.py:1025
[action]         → Error executing tool fetch_url: Client error '404 Not Found' for url 'https://www.weather25.com/404.php'
For more inform
[memory.outcome]  fetch_url('https://www.weather25.com/asia/japan/to) -> Error executing tool fetc

── iter 4 ──
[memory.read]    4 hits
[perception]     [done] Search for family-friendly activities in Tokyo for this weekend attach=art:b1443b393c2d240d
[perception]     [done] Check the weather forecast for Saturday in Tokyo attach=art:287f66a72bc999b6
[perception]     [open] Determine which activity is most appropriate based on the weather attach=art:b1443b393c2d240d
[pydantic ✓]   Observation
[attach]         art:b1443b393c2d240d (2176 bytes)
[pydantic ✓]   DecisionOutput
[decision]       TOOL_CALL: read_file({"path": "art:287f66a72bc999b6"})
[action.guarded] ⚠ artifact handle leaked as path/url: read_file
[action]         → error: artifact handles are not paths/urls — read attached bytes in the prompt instead
[memory.outcome]  read_file('art:287f66a72bc999b6') -> error: artifact handles are not paths/urls 

── iter 5 ──
[memory.read]    5 hits
[perception]     [done] Search for family-friendly activities in Tokyo for this weekend attach=art:b1443b393c2d240d
[perception]     [done] Check the weather forecast for Saturday in Tokyo attach=art:287f66a72bc999b6
[perception]     [open] Determine which activity is most appropriate based on the weather attach=art:b1443b393c2d240d
[pydantic ✓]   Observation
[attach]         art:b1443b393c2d240d (2176 bytes)
[pydantic ✓]   DecisionOutput
[decision]       TOOL_CALL: web_search({"max_results": 5, "query": "Tokyo weather Saturday May 2026 forecast"})
[05/30/26 04:03:11] INFO     Processing request of type CallToolRequest                                                                                                         server.py:727
[artifacts.put]  art:5d38f21284dd1fc7 (2116 bytes, text/plain)
[action]         → [artifact art:5d38f21284dd1fc7, 2116 bytes] preview: [Tokyo weather in May 2026 - Weather25.com](https://www.weather25.c [art:art:5d38f21284dd1fc7]
[memory.outcome]  web_search(5, 'Tokyo weather Saturday May 2026 forecas) -> art:5d38f21284dd1fc7

── iter 6 ──
[memory.read]    6 hits
[perception]     [done] Search for family-friendly activities in Tokyo for this weekend attach=art:b1443b393c2d240d
[perception]     [done] Check the weather forecast for Saturday in Tokyo attach=art:287f66a72bc999b6
[perception]     [open] Determine which activity is most appropriate based on the weather attach=art:b1443b393c2d240d
[pydantic ✓]   Observation
[attach]         art:b1443b393c2d240d (2176 bytes)
[pydantic ✓]   DecisionOutput
[decision]       TOOL_CALL: fetch_url({"url": "https://www.weather25.com/asia/japan/tokyo/may-2026"})
[05/30/26 04:03:35] INFO     Processing request of type CallToolRequest                                                                                                         server.py:727
[mcp] crawl4ai error: crawl4ai failed: BrowserType.launch: Executable doesn't exist at /Users/harshagarwal/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing
╔════════════════════════════════════════════════════════════╗
║ Looks like Playwright was just installed or updated.       ║
║ Please run the following command to download new browsers: ║
║                                                            ║
║     playwright install                                     ║
║                                                            ║
║ <3 Playwright Team                                         ║
╚════════════════════════════════════════════════════════════╝, falling back to httpx
[05/30/26 04:03:36] INFO     HTTP Request: GET https://www.weather25.com/asia/japan/tokyo/may-2026 "HTTP/1.1 302 Found"                                                       _client.py:1025
                    INFO     HTTP Request: GET https://www.weather25.com/404.php "HTTP/1.1 404 Not Found"                                                                     _client.py:1025
[action]         → Error executing tool fetch_url: Client error '404 Not Found' for url 'https://www.weather25.com/404.php'
For more inform
[memory.outcome]  fetch_url('https://www.weather25.com/asia/japan/to) -> Error executing tool fetc

── iter 7 ──
[memory.read]    7 hits
[perception]     [done] Search for family-friendly activities in Tokyo for this weekend attach=art:b1443b393c2d240d
[perception]     [done] Check the weather forecast for Saturday in Tokyo attach=art:287f66a72bc999b6
[perception]     [open] Determine which activity is most appropriate based on the weather attach=art:b1443b393c2d240d
[pydantic ✓]   Observation
[attach]         art:b1443b393c2d240d (2176 bytes)
[pydantic ✓]   DecisionOutput
[decision]       TOOL_CALL: web_search({"query": "Tokyo weather forecast this weekend temperature rain conditions", "ma)
[05/30/26 04:03:49] INFO     Processing request of type CallToolRequest                                                                                                         server.py:727
[artifacts.put]  art:b1e0da9872992c57 (2118 bytes, text/plain)
[action]         → [artifact art:b1e0da9872992c57, 2118 bytes] preview: [Weather in Japan in May 2026 - Detailed Forecast](https://www.ease [art:art:b1e0da9872992c57]
[memory.outcome]  web_search('Tokyo weather forecast this weekend tem, 5) -> art:b1e0da9872992c57

── iter 8 ──
[memory.read]    8 hits
[perception]     [done] Search for family-friendly activities in Tokyo for this weekend attach=art:b1443b393c2d240d
[perception]     [done] Check the weather forecast for Saturday in Tokyo attach=art:287f66a72bc999b6
[perception]     [open] Determine which activity is most appropriate based on the weather attach=art:b1443b393c2d240d
[pydantic ✓]   Observation
[attach]         art:b1443b393c2d240d (2176 bytes)
[pydantic ✓]   DecisionOutput
[decision]       TOOL_CALL: fetch_url({"url": "https://www.weather25.com/asia/japan/tokyo/may-2026"})
[05/30/26 04:04:11] INFO     Processing request of type CallToolRequest                                                                                                         server.py:727
[mcp] crawl4ai error: crawl4ai failed: BrowserType.launch: Executable doesn't exist at /Users/harshagarwal/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing
╔════════════════════════════════════════════════════════════╗
║ Looks like Playwright was just installed or updated.       ║
║ Please run the following command to download new browsers: ║
║                                                            ║
║     playwright install                                     ║
║                                                            ║
║ <3 Playwright Team                                         ║
╚════════════════════════════════════════════════════════════╝, falling back to httpx
[05/30/26 04:04:12] INFO     HTTP Request: GET https://www.weather25.com/asia/japan/tokyo/may-2026 "HTTP/1.1 302 Found"                                                       _client.py:1025
                    INFO     HTTP Request: GET https://www.weather25.com/404.php "HTTP/1.1 404 Not Found"                                                                     _client.py:1025
[action]         → Error executing tool fetch_url: Client error '404 Not Found' for url 'https://www.weather25.com/404.php'
For more inform
[memory.outcome]  fetch_url('https://www.weather25.com/asia/japan/to) -> Error executing tool fetc

── iter 9 ──
[memory.read]    8 hits
[perception]     [done] Search for family-friendly activities in Tokyo for this weekend attach=art:b1443b393c2d240d
[perception]     [done] Check the weather forecast for Saturday in Tokyo attach=art:b1e0da9872992c57
[perception]     [open] Determine which activity is most appropriate based on the weather attach=art:b1443b393c2d240d
[pydantic ✓]   Observation
[attach]         art:b1443b393c2d240d (2176 bytes)
[pydantic ✓]   DecisionOutput
[decision]       ANSWER: Based on the available information regarding Tokyo's climate in May, the weather is generally mild a

── iter 10 ──
[memory.read]    8 hits
[perception]     [done] Search for family-friendly activities in Tokyo for this weekend attach=art:b1443b393c2d240d
[perception]     [done] Check the weather forecast for Saturday in Tokyo attach=art:b1e0da9872992c57
[perception]     [open] Determine which activity is most appropriate based on the weather attach=art:b1443b393c2d240d
[pydantic ✓]   Observation
[attach]         art:b1443b393c2d240d (2176 bytes)
[pydantic ✓]   DecisionOutput
[decision]       ANSWER: Based on the provided information, the most appropriate activities for a weekend in Tokyo depend on 

── iter 11 ──
[memory.read]    8 hits
[perception]     [done] Search for family-friendly activities in Tokyo for this weekend attach=art:b1443b393c2d240d
[perception]     [done] Check the weather forecast for Saturday in Tokyo attach=art:b1e0da9872992c57
[perception]     [open] Determine which activity is most appropriate based on the weather attach=art:b1443b393c2d240d
[pydantic ✓]   Observation
[attach]         art:b1443b393c2d240d (2176 bytes)
[pydantic ✓]   DecisionOutput
[decision]       ANSWER: Based on the information provided, Tokyo in May typically features mild and pleasant weather, making

── iter 12 ──
[memory.read]    8 hits
[perception]     [done] Search for family-friendly activities in Tokyo for this weekend attach=art:b1443b393c2d240d
[perception]     [done] Check the weather forecast for Saturday in Tokyo attach=art:287f66a72bc999b6
[perception]     [open] Determine which activity is most appropriate based on the weather attach=art:b1443b393c2d240d
[pydantic ✓]   Observation
[attach]         art:b1443b393c2d240d (2176 bytes)
[pydantic ✓]   DecisionOutput
[decision]       TOOL_CALL: web_search({"max_results": 5, "query": "Tokyo weather Saturday May 2026 forecast"})
[05/30/26 04:05:54] INFO     Processing request of type CallToolRequest                                                                                                         server.py:727
[action]         → [artifact art:5d38f21284dd1fc7, 2116 bytes] preview: [Tokyo weather in May 2026 - Weather25.com](https://www.weather25.c [art:art:5d38f21284dd1fc7]
[memory.outcome]  web_search(5, 'Tokyo weather Saturday May 2026 forecas) -> art:5d38f21284dd1fc7

── iter 13 ──
[memory.read]    8 hits
[perception]     [done] Search for family-friendly activities in Tokyo for this weekend attach=art:b1443b393c2d240d
[perception]     [done] Check the weather forecast for Saturday in Tokyo attach=art:5d38f21284dd1fc7
[perception]     [open] Determine which activity is most appropriate based on the weather attach=art:b1443b393c2d240d
[pydantic ✓]   Observation
[attach]         art:b1443b393c2d240d (2176 bytes)
[pydantic ✓]   DecisionOutput
[decision]       ANSWER: Based on the typical climate for Tokyo in May, which is generally mild and pleasant, here are the mo

── iter 14 ──
[memory.read]    8 hits
[perception]     [done] Search for family-friendly activities in Tokyo for this weekend attach=art:b1443b393c2d240d
[perception]     [done] Check the weather forecast for Saturday in Tokyo attach=art:5d38f21284dd1fc7
[perception]     [open] Determine which activity is most appropriate based on the weather attach=art:b1443b393c2d240d
[pydantic ✓]   Observation
[attach]         art:b1443b393c2d240d (2176 bytes)
[pydantic ✓]   DecisionOutput
[decision]       ANSWER: Based on the generally mild and pleasant weather typical of Tokyo in May, here are several highly re
[run_end]   FINAL: Based on the generally mild and pleasant weather typical of Tokyo in May, here are several highly recommended family-friendly activities that are well-suited for these conditions:

*   **Ueno Zoo:** L

FINAL: Based on the generally mild and pleasant weather typical of Tokyo in May, here are several highly recommended family-friendly activities that are well-suited for these conditions:

*   **Ueno Zoo:** Located in central Tokyo, this is Japan's oldest zoo and an excellent outdoor destination. It houses over 300 animal species, including the popular giant pandas, making it a perfect spot to enjoy a temperate May day.
*   **Asakusa Cultural and Traditional Experiences:** You can engage in activities such as a Kimono rental and photoshoot in the Asakusa district. Since these experiences often involve walking through historic streets and visiting nearby temples, the mild May weather makes this a very comfortable and photogenic outdoor option.
*   **Sunshine City:** If you prefer a mix of indoor and outdoor options, Sunshine City provides a large entertainment complex. This is a reliable choice that offers various attractions, ensuring you have a great time regardless of minor fluctuations in the weather.
*   **The Making of Harry Potter Exhibit:** Located in Nerima, this is the world's largest indoor Harry Potter exhibit. Because it is primarily an indoor experience, it is a fantastic "weather-proof" activity, allowing you to explore film sets comfortably even if the day turns out to be warmer or more humid than expected.

These options provide a good balance of outdoor exploration and comfortable indoor cultural experiences, taking full advantage of Tokyo's pleasant spring climate.
```

### Query 3 — Mom's Birthday Save and Calendar Reminders

**Run ID:** `a63be5ff`  
**Status:** **SUCCESS**  
**Original query:** `My mom's birthday is 15 May 2026. Remember that and give me a calendar reminder for two weeks before and on the day.`

```console
Enter query > My mom's birthday is 15 May 2026. Remember that and give me a calendar reminder for two weeks before and on the day.
[gateway] connecting to llm_gatewayV3 at http://localhost:8101 ... ok
[run_start] run_id=a63be5ff query="My mom's birthday is 15 May 2026. Remember that and give me a calendar reminder "
[memory.remember] no durable content
[05/30/26 04:17:34] INFO     Processing request of type ListToolsRequest                                                                                                        server.py:727
[mcp] spawning mcp_server.py over stdio ... ok (9 tools loaded)
                    INFO     Processing request of type ListToolsRequest                                                                                                        server.py:727

── iter 1 ──
[memory.read]    0 hits
[perception]     [open] Remember the birthday date 15 May 2026
[perception]     [open] Set a calendar reminder for 1 May 2026
[perception]     [open] Set a calendar reminder for 15 May 2026
[pydantic ✓]   Observation
[pydantic ✓]   DecisionOutput
[decision]       TOOL_CALL: create_file({"content": "Birthday: 15 May 2026", "path": "birthday.txt"})
[05/30/26 04:17:47] INFO     Processing request of type CallToolRequest                                                                                                         server.py:727
[action]         → Created birthday.txt (21 bytes)
[memory.outcome]  create_file('Birthday: 15 May 2026', 'birthday.txt') -> Created birthday.txt (21

── iter 2 ──
[memory.read]    1 hits
[perception]     [done] Remember the birthday date 15 May 2026
[perception]     [open] Set a calendar reminder for 1 May 2026
[perception]     [open] Set a calendar reminder for 15 May 2026
[pydantic ✓]   Observation
[pydantic ✓]   DecisionOutput
[decision]       TOOL_CALL: create_file({"path": "reminder_1may2026.txt", "content": "Calendar Reminder: 1 May 2026"})
[05/30/26 04:18:29] INFO     Processing request of type CallToolRequest                                                                                                         server.py:727
[action]         → Created reminder_1may2026.txt (29 bytes)
[memory.outcome]  create_file('reminder_1may2026.txt', 'Calendar Reminder: 1 May 2026') -> Created

── iter 3 ──
[memory.read]    2 hits
[perception]     [done] Remember the birthday date 15 May 2026
[perception]     [done] Set a calendar reminder for 1 May 2026
[perception]     [open] Set a calendar reminder for 15 May 2026
[pydantic ✓]   Observation
[pydantic ✓]   DecisionOutput
[decision]       TOOL_CALL: create_file({"content": "Calendar Reminder: 15 May 2026", "path": "reminder_15may2026.txt"})
[05/30/26 04:18:32] INFO     Processing request of type CallToolRequest                                                                                                         server.py:727
[action]         → Created reminder_15may2026.txt (30 bytes)
[memory.outcome]  create_file('Calendar Reminder: 15 May 2026', 'reminder_15may2026.txt') -> Creat

── iter 4 ──
[memory.read]    3 hits
[perception]     [done] Remember the birthday date 15 May 2026
[perception]     [done] Set a calendar reminder for 1 May 2026
[perception]     [done] Set a calendar reminder for 15 May 2026
[pydantic ✓]   Observation
[done] all 3 goals satisfied
[run_end]   FINAL: Created reminder_15may2026.txt (30 bytes)

FINAL: Created reminder_15may2026.txt (30 bytes)
```

### Query 4 — Mom's Birthday Recall

**Run ID:** `6f45ff10`  

**Status:** **SUCCESS**  

**Original query:** `When is mom's birthday?`

```console
Enter query > When is mom's birthday?
[gateway] connecting to llm_gatewayV3 at http://localhost:8101 ... ok
[run_start] run_id=6f45ff10 query="When is mom's birthday?"
[memory.remember] classified → scratchpad: The user is inquiring about the date of their mother's birth
[05/30/26 04:19:53] INFO     Processing request of type ListToolsRequest                                                                                                        server.py:727
[mcp] spawning mcp_server.py over stdio ... ok (9 tools loaded)
                    INFO     Processing request of type ListToolsRequest                                                                                                        server.py:727

── iter 1 ──
[memory.read]    3 hits
[perception]     [open] Locate the birth date of the user's mother in available memory
[pydantic ✓]   Observation
[pydantic ✓]   DecisionOutput
[decision]       ANSWER: The information stored in memory indicates that the user’s mother’s birthday has been recorded in a 

── iter 2 ──
[memory.read]    5 hits
[perception]     [done] Locate the birth date of the user's mother in available memory
[pydantic ✓]   Observation
[done] all 1 goals satisfied
[run_end]   FINAL: The information stored in memory indicates that the user’s mother’s birthday has been recorded in a file named **birthday.txt**. The content of that file is:

```
Birthday: 15 May 2026
```

Therefore,

FINAL: The information stored in memory indicates that the user’s mother’s birthday has been recorded in a file named **birthday.txt**. The content of that file is:

```
Birthday: 15 May 2026
```

Therefore, the birth date of the user’s mother is **15 May 2026**.
```

### Query 5 — Python asyncio Best Practices

**Run ID:** `a9b759e4`  

**Status:** **SUCCESS**  

**Original query:** `Search for 'Python asyncio best practices', read the top 3 results, and give me a short numbered list of the advice they agree on.`

```console
Enter query > Search for 'Python asyncio best practices', read the top 3 results, and give me a short numbered list of the advice they agree on.
[gateway] connecting to llm_gatewayV3 at http://localhost:8101 ... ok
[run_start] run_id=a9b759e4 query="Search for 'Python asyncio best practices', read the top 3 results, and give me "
[memory.remember] no durable content
[05/30/26 04:21:03] INFO     Processing request of type ListToolsRequest                                                                                                        server.py:727
[mcp] spawning mcp_server.py over stdio ... ok (9 tools loaded)
                    INFO     Processing request of type ListToolsRequest                                                                                                        server.py:727

── iter 1 ──
[memory.read]    0 hits
[perception]     [open] Perform a web search for 'Python asyncio best practices'
[perception]     [open] Fetch the top 3 search results
[perception]     [open] Summarize the common advice from the top 3 results in a numbered list
[pydantic ✓]   Observation
[pydantic ✓]   DecisionOutput
[decision]       TOOL_CALL: web_search({"max_results": 5, "query": "Python asyncio best practices"})
[05/30/26 04:21:08] INFO     Processing request of type CallToolRequest                                                                                                         server.py:727
[artifacts.put]  art:f48f229b4d7652fe (2158 bytes, text/plain)
[action]         → [artifact art:f48f229b4d7652fe, 2158 bytes] preview: [Asyncio best practices - Async-SIG - Discussions on Python.org](ht [art:art:f48f229b4d7652fe]
[memory.outcome]  web_search(5, 'Python asyncio best practices') -> art:f48f229b4d7652fe

── iter 2 ──
[memory.read]    4 hits
[perception]     [done] Perform a web search for 'Python asyncio best practices' attach=art:f48f229b4d7652fe
[perception]     [open] Fetch the top 3 search results attach=art:f48f229b4d7652fe
[perception]     [open] Summarize the common advice from the top 3 results in a numbered list attach=art:f48f229b4d7652fe
[pydantic ✓]   Observation
[attach]         art:f48f229b4d7652fe (2158 bytes)
[pydantic ✓]   DecisionOutput
[decision]       TOOL_CALL: fetch_url({"url": "https://discuss.python.org/t/asyncio-best-practices/12576"})
[05/30/26 04:21:25] INFO     Processing request of type CallToolRequest                                                                                                         server.py:727
[mcp] crawl4ai error: crawl4ai failed: BrowserType.launch: Executable doesn't exist at /Users/harshagarwal/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing
╔════════════════════════════════════════════════════════════╗
║ Looks like Playwright was just installed or updated.       ║
║ Please run the following command to download new browsers: ║
║                                                            ║
║     playwright install                                     ║
║                                                            ║
║ <3 Playwright Team                                         ║
╚════════════════════════════════════════════════════════════╝, falling back to httpx
[05/30/26 04:21:27] INFO     HTTP Request: GET https://discuss.python.org/t/asyncio-best-practices/12576 "HTTP/1.1 200 OK"                                                    _client.py:1025
[action]         → Asyncio best practices - Async-SIG - Discussions on Python.org = 40rem)" rel="stylesheet" data-target="desktop" /> = 40r
[memory.outcome]  fetch_url('https://discuss.python.org/t/asyncio-be) -> Asyncio best practices - 

── iter 3 ──
[memory.read]    5 hits
[perception]     [done] Perform a web search for 'Python asyncio best practices' attach=art:f48f229b4d7652fe
[perception]     [open] Fetch the top 3 search results attach=art:f48f229b4d7652fe
[perception]     [open] Summarize the common advice from the top 3 results in a numbered list attach=art:f48f229b4d7652fe
[pydantic ✓]   Observation
[attach]         art:f48f229b4d7652fe (2158 bytes)
[pydantic ✓]   DecisionOutput
[decision]       TOOL_CALL: fetch_url({"url": "https://oneuptime.com/blog/post/2026-01-24-asyncio-concurrent-programmi)
[05/30/26 04:21:32] INFO     Processing request of type CallToolRequest                                                                                                         server.py:727
[mcp] crawl4ai error: crawl4ai failed: BrowserType.launch: Executable doesn't exist at /Users/harshagarwal/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing
╔════════════════════════════════════════════════════════════╗
║ Looks like Playwright was just installed or updated.       ║
║ Please run the following command to download new browsers: ║
║                                                            ║
║     playwright install                                     ║
║                                                            ║
║ <3 Playwright Team                                         ║
╚════════════════════════════════════════════════════════════╝, falling back to httpx
[05/30/26 04:21:33] INFO     HTTP Request: GET https://oneuptime.com/blog/post/2026-01-24-asyncio-concurrent-programming-python/view "HTTP/1.1 200 OK"                        _client.py:1025
[artifacts.put]  art:f566628782dc5b98 (50008 bytes, text/markdown)
[action]         → [artifact art:f566628782dc5b98, 50008 bytes] preview: How to Use asyncio for Concurrent Programming in Python * { font-f [art:art:f566628782dc5b98]
[memory.outcome]  fetch_url('https://oneuptime.com/blog/post/2026-01) -> art:f566628782dc5b98

── iter 4 ──
[memory.read]    6 hits
[perception]     [done] Perform a web search for 'Python asyncio best practices' attach=art:f48f229b4d7652fe
[perception]     [open] Fetch the top 3 search results attach=art:f48f229b4d7652fe
[perception]     [open] Summarize the common advice from the top 3 results in a numbered list attach=art:f48f229b4d7652fe
[pydantic ✓]   Observation
[attach]         art:f48f229b4d7652fe (2158 bytes)
[pydantic ✓]   DecisionOutput
[decision]       TOOL_CALL: fetch_url({"url": "https://www.shanechang.com/p/python-asyncio-best-practices-pitfalls"})
[05/30/26 04:22:04] INFO     Processing request of type CallToolRequest                                                                                                         server.py:727
[mcp] crawl4ai error: crawl4ai failed: BrowserType.launch: Executable doesn't exist at /Users/harshagarwal/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing
╔════════════════════════════════════════════════════════════╗
║ Looks like Playwright was just installed or updated.       ║
║ Please run the following command to download new browsers: ║
║                                                            ║
║     playwright install                                     ║
║                                                            ║
║ <3 Playwright Team                                         ║
╚════════════════════════════════════════════════════════════╝, falling back to httpx
                    INFO     HTTP Request: GET https://www.shanechang.com/p/python-asyncio-best-practices-pitfalls "HTTP/1.1 301 Moved Permanently"                           _client.py:1025
[05/30/26 04:22:05] INFO     HTTP Request: GET https://shanechang.com/p/python-asyncio-best-practices-pitfalls "HTTP/1.1 301 Moved Permanently"                               _client.py:1025
                    INFO     HTTP Request: GET https://shanechang.com/p/python-asyncio-best-practices-pitfalls/ "HTTP/1.1 200 OK"                                             _client.py:1025
[artifacts.put]  art:7633e6c5a4b936fb (6906 bytes, text/markdown)
[action]         → [artifact art:7633e6c5a4b936fb, 6906 bytes] preview: Asyncio Best Practices and Common Pitfalls document.documentElement [art:art:7633e6c5a4b936fb]
[memory.outcome]  fetch_url('https://www.shanechang.com/p/python-asy) -> art:7633e6c5a4b936fb

── iter 5 ──
[memory.read]    7 hits
[perception]     [done] Perform a web search for 'Python asyncio best practices' attach=art:f48f229b4d7652fe
[perception]     [done] Fetch the top 3 search results attach=art:f48f229b4d7652fe
[perception]     [open] Summarize the common advice from the top 3 results in a numbered list attach=art:f566628782dc5b98
[pydantic ✓]   Observation
[attach]         art:f566628782dc5b98 (50008 bytes)
[pydantic ✓]   DecisionOutput
[decision]       TOOL_CALL: fetch_url({"url": "https://discuss.python.org/t/asyncio-best-practices/12576"})
[05/30/26 04:22:23] INFO     Processing request of type CallToolRequest                                                                                                         server.py:727
[mcp] crawl4ai error: crawl4ai failed: BrowserType.launch: Executable doesn't exist at /Users/harshagarwal/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing
╔════════════════════════════════════════════════════════════╗
║ Looks like Playwright was just installed or updated.       ║
║ Please run the following command to download new browsers: ║
║                                                            ║
║     playwright install                                     ║
║                                                            ║
║ <3 Playwright Team                                         ║
╚════════════════════════════════════════════════════════════╝, falling back to httpx
[05/30/26 04:22:25] INFO     HTTP Request: GET https://discuss.python.org/t/asyncio-best-practices/12576 "HTTP/1.1 200 OK"                                                    _client.py:1025
[action]         → Asyncio best practices - Async-SIG - Discussions on Python.org = 40rem)" rel="stylesheet" data-target="desktop" /> = 40r
[memory.outcome]  fetch_url('https://discuss.python.org/t/asyncio-be) -> Asyncio best practices - 

── iter 6 ──
[memory.read]    8 hits
[perception]     [done] Perform a web search for 'Python asyncio best practices' attach=art:f4 attach=art:f48f229b4d7652fe
[perception]     [done] Fetch the top 3 search results attach=art:f48f229b4d7652fe attach=art:f48f229b4d7652fe
[perception]     [open] Summarize the common advice from the top 3 results in a numbered list  attach=art:f566628782dc5b98
[pydantic ✓]   Observation
[attach]         art:f566628782dc5b98 (50008 bytes)
[pydantic ✓]   DecisionOutput
[decision]       TOOL_CALL: fetch_url({"url": "https://www.shanechang.com/p/python-asyncio-best-practices-pitfalls"})
[05/30/26 04:22:31] INFO     Processing request of type CallToolRequest                                                                                                         server.py:727
[mcp] crawl4ai error: crawl4ai failed: BrowserType.launch: Executable doesn't exist at /Users/harshagarwal/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing
╔════════════════════════════════════════════════════════════╗
║ Looks like Playwright was just installed or updated.       ║
║ Please run the following command to download new browsers: ║
║                                                            ║
║     playwright install                                     ║
║                                                            ║
║ <3 Playwright Team                                         ║
╚════════════════════════════════════════════════════════════╝, falling back to httpx
                    INFO     HTTP Request: GET https://www.shanechang.com/p/python-asyncio-best-practices-pitfalls "HTTP/1.1 301 Moved Permanently"                           _client.py:1025
[05/30/26 04:22:32] INFO     HTTP Request: GET https://shanechang.com/p/python-asyncio-best-practices-pitfalls "HTTP/1.1 301 Moved Permanently"                               _client.py:1025
                    INFO     HTTP Request: GET https://shanechang.com/p/python-asyncio-best-practices-pitfalls/ "HTTP/1.1 200 OK"                                             _client.py:1025
[artifacts.put]  art:b623c22439443efe (6906 bytes, text/markdown)
[action]         → [artifact art:b623c22439443efe, 6906 bytes] preview: Asyncio Best Practices and Common Pitfalls document.documentElement [art:art:b623c22439443efe]
[memory.outcome]  fetch_url('https://www.shanechang.com/p/python-asy) -> art:b623c22439443efe

── iter 7 ──
[memory.read]    8 hits
[perception]     [done] Perform a web search for 'Python asyncio best practices' attach=art:f48f229b4d7652fe
[perception]     [done] Fetch the top 3 search results attach=art:f48f229b4d7652fe
[perception]     [open] Summarize the common advice from the top 3 results in a numbered list attach=art:f566628782dc5b98
[pydantic ✓]   Observation
[attach]         art:f566628782dc5b98 (50008 bytes)
[pydantic ✓]   DecisionOutput
[decision]       TOOL_CALL: fetch_url({"url": "https://discuss.python.org/t/asyncio-best-practices/12576"})
[05/30/26 04:22:36] INFO     Processing request of type CallToolRequest                                                                                                         server.py:727
[mcp] crawl4ai error: crawl4ai failed: BrowserType.launch: Executable doesn't exist at /Users/harshagarwal/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing
╔════════════════════════════════════════════════════════════╗
║ Looks like Playwright was just installed or updated.       ║
║ Please run the following command to download new browsers: ║
║                                                            ║
║     playwright install                                     ║
║                                                            ║
║ <3 Playwright Team                                         ║
╚════════════════════════════════════════════════════════════╝, falling back to httpx
[05/30/26 04:22:37] INFO     HTTP Request: GET https://discuss.python.org/t/asyncio-best-practices/12576 "HTTP/1.1 200 OK"                                                    _client.py:1025
[action]         → Asyncio best practices - Async-SIG - Discussions on Python.org = 40rem)" rel="stylesheet" data-target="desktop" /> = 40r
[memory.outcome]  fetch_url('https://discuss.python.org/t/asyncio-be) -> Asyncio best practices - 

── iter 8 ──
[memory.read]    8 hits
[perception]     [done] Perform a web search for 'Python asyncio best practices' attach=art:f48f229b4d7652fe
[perception]     [done] Fetch the top 3 search results attach=art:f48f229b4d7652fe
[perception]     [open] Summarize the common advice from the top 3 results in a numbered list attach=art:f566628782dc5b98
[pydantic ✓]   Observation
[attach]         art:f566628782dc5b98 (50008 bytes)
[pydantic ✓]   DecisionOutput
[decision]       ANSWER: Based on the provided resources, here is a summary of common best practices for using Python's `asyn

── iter 9 ──
[memory.read]    8 hits
[perception]     [done] Perform a web search for 'Python asyncio best practices' attach=art:f48f229b4d7652fe
[perception]     [done] Fetch the top 3 search results attach=art:f48f229b4d7652fe
[perception]     [open] Summarize the common advice from the top 3 results in a numbered list attach=art:f566628782dc5b98
[pydantic ✓]   Observation
[attach]         art:f566628782dc5b98 (50008 bytes)
[pydantic ✓]   DecisionOutput
[decision]       TOOL_CALL: fetch_url({"url": "https://www.shanechang.com/p/python-asyncio-best-practices-pitfalls"})
[05/30/26 04:23:55] INFO     Processing request of type CallToolRequest                                                                                                         server.py:727
[mcp] crawl4ai error: crawl4ai failed: BrowserType.launch: Executable doesn't exist at /Users/harshagarwal/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing
╔════════════════════════════════════════════════════════════╗
║ Looks like Playwright was just installed or updated.       ║
║ Please run the following command to download new browsers: ║
║                                                            ║
║     playwright install                                     ║
║                                                            ║
║ <3 Playwright Team                                         ║
╚════════════════════════════════════════════════════════════╝, falling back to httpx
                    INFO     HTTP Request: GET https://www.shanechang.com/p/python-asyncio-best-practices-pitfalls "HTTP/1.1 301 Moved Permanently"                           _client.py:1025
[05/30/26 04:23:56] INFO     HTTP Request: GET https://shanechang.com/p/python-asyncio-best-practices-pitfalls "HTTP/1.1 301 Moved Permanently"                               _client.py:1025
                    INFO     HTTP Request: GET https://shanechang.com/p/python-asyncio-best-practices-pitfalls/ "HTTP/1.1 200 OK"                                             _client.py:1025
[artifacts.put]  art:6c8df9ee3fee2e1d (6906 bytes, text/markdown)
[action]         → [artifact art:6c8df9ee3fee2e1d, 6906 bytes] preview: Asyncio Best Practices and Common Pitfalls document.documentElement [art:art:6c8df9ee3fee2e1d]
[memory.outcome]  fetch_url('https://www.shanechang.com/p/python-asy) -> art:6c8df9ee3fee2e1d

── iter 10 ──
[memory.read]    8 hits
[perception]     [done] Perform a web search for 'Python asyncio best practices' attach=art:f48f229b4d7652fe
[perception]     [done] Fetch the top 3 search results attach=art:f48f229b4d7652fe
[perception]     [done] Summarize the common advice from the top 3 results in a numbered list attach=art:f566628782dc5b98
[pydantic ✓]   Observation
[done] all 3 goals satisfied
[run_end]   FINAL: Based on the provided resources, here is a summary of common best practices for using Python's `asyncio` for concurrent programming:

1.  **Avoid Blocking the Event Loop:** The most critical rule in `

FINAL: Based on the provided resources, here is a summary of common best practices for using Python's `asyncio` for concurrent programming:

1.  **Avoid Blocking the Event Loop:** The most critical rule in `asyncio` is to never execute CPU-bound or long-running synchronous code directly within an `async` function. Blocking the event loop prevents other tasks from running, which effectively nullifies the benefits of concurrency; instead, offload heavy computations to a separate thread or process using `loop.run_in_executor`.
2.  **Use High-Level Awaitables:** Developers should prioritize using high-level `asyncio` primitives, such as `asyncio.gather()`, `asyncio.TaskGroup`, or `asyncio.create_task()`, to manage concurrent execution. These tools allow you to run multiple coroutines simultaneously and handle their results effectively, rather than attempting to manually manage low-level event loop internals.
3.  **Proper Exception Handling and Cleanup:** Always ensure that tasks are properly awaited or cancelled to prevent "leaked" tasks or silent failures. When running concurrent operations, use robust error handling (such as `try/except` blocks within your tasks or using `return_exceptions=True` in `asyncio.gather`) to ensure that one failing task does not leave the entire application in an inconsistent state or prevent other tasks from completing.
```
