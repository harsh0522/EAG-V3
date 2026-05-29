# EAGV3 Session 7 — RAG Agent (assignment7)

A four-role agentic system (Perception → Decision → Action → Memory) extended with dense vector retrieval through FAISS. Built on top of Session 6.

---

## Setup

### 1. Prerequisites

```bash
# Install Ollama (https://ollama.com)
ollama pull nomic-embed-text
ollama serve   # keep running in a separate terminal

# Python deps
pip install -r requirements.txt
# or with uv: uv pip install -r requirements.txt
```

### 2. Environment variables

Copy `.env.example` to `.env` in the **Session 7 root** (one level up from this folder) and fill in your keys:

```bash
cp ../.env.example ../.env
# edit ../.env — add GEMINI_API_KEY, TAVILY_API_KEY, etc.
```

The `.env` file must stay in `Session 7 - Memory and Retrieval/` (never inside `assignment7/`).

### 3. Start the gateway

```bash
cd ../llm_gatewayV7
uv run python main.py   # runs on port 8107
```

### 4. Run the agent

```bash
cd assignment7/

# Interactive REPL
python agent.py

# Single query + trace saved
python agent.py "Fetch https://en.wikipedia.org/wiki/Claude_Shannon ..." \
  --trace base/A_shannon.json

# Index a corpus directory
python agent.py --index corpus/
```

### 5. View the explainer webpage

```bash
cd assignment7/
python -m http.server 8080
# Open: http://localhost:8080/viewer.html
```

---

## Architecture (S7 changes over S6)

| Component | S6 | S7 |
|-----------|----|----|
| Gateway | V3 (port 8101) | V7 (port 8107) |
| Gateway embed | — | `POST /v1/embed` (Ollama → Gemini fallback, 768-dim) |
| MemoryItem | no embedding | `embedding: list[float] \| None` |
| Memory read | keyword overlap | **vector-first** (FAISS IndexFlatIP) + keyword fallback |
| New MCP tools | — | `index_document`, `search_knowledge` |
| Trace logging | SSE dashboard | `TraceLogger` → `traces/*.json` + `*.log` |

**Architectural invariant:** `grep -E "(index_document|search_knowledge|fetch_url|search_web|list_dir|read_file)" perception.py` — zero matches inside the SYSTEM string.

---

## File structure

```
assignment7/
├── agent.py              # agent loop + TraceLogger
├── perception.py         # goal decomposition (no MCP tool names in SYSTEM)
├── decision.py           # single LLM call per goal
├── action.py             # MCP dispatch + artifact guard
├── memory.py             # FAISS vector search + keyword fallback + add_fact
├── mcp_server.py         # 11 tools including index_document + search_knowledge
├── schemas.py            # MemoryItem (with embedding), Goal, DecisionOutput, etc.
├── logger.py             # structured event logging
├── viewer.html           # single-file explainer webpage
├── prompts/
│   ├── perception_system.md
│   └── decision_system.md
├── papers/               # 5 academic paper summaries (base queries E–H)
│   ├── attention.md
│   ├── chain_of_thought.md
│   ├── react.md
│   ├── dpo.md
│   └── lora.md
├── corpus/               # 52 AI Engineering Pattern documents (custom queries)
│   ├── 01_few_shot_prompting.md … 52_embedding_space_analysis.md
├── traces/
│   ├── base/             # 10 JSON + 10 .log files (queries A–H)
│   └── custom/           # 10 JSON + 10 .log files (5 custom queries × 2)
├── state/                # runtime (gitignored)
│   ├── memory.json
│   ├── index.faiss
│   └── index_ids.json
└── requirements.txt
```

---

## Base Queries (A–H)

Run each verbatim. Save trace with `--trace base/<name>.json`.

| ID | Query (verbatim) | Bound |
|----|-------------------|-------|
| A | `Fetch https://en.wikipedia.org/wiki/Claude_Shannon and tell me his birth date, death date, and three key contributions to information theory.` | 3 |
| B | `Find 3 family-friendly things to do in Tokyo this weekend. Check Saturday's weather forecast there and tell me which one is most appropriate.` | 8 |
| C-run1 | `My mom's birthday is 15 May 2026. Remember that and create reminders for two weeks before and on the day.` | 4 |
| C-run2 | `When is mom's birthday?` *(fresh process, keep state/)* | 3 |
| D | `Search for "Python asyncio best practices", read the top 3 results, and give me a short numbered list of the advice they agree on.` | 6 |
| E | `Index the file papers/attention.md and tell me what the three key contributions of the Transformer architecture are according to this paper.` | 5 |
| F-run1 | `Index every .md file under papers/. Confirm how many chunks were indexed in total.` | 11 |
| F-run2 | `Across the papers I have indexed, what do they say about chain-of-thought reasoning?` *(keep state/)* | 3 |
| G | `Across these papers, how do they handle the credit assignment problem?` | 4 |
| H | `Compare how the ReAct paper and the Chain-of-Thought paper differ in their treatment of intermediate reasoning.` | 3 |

**Notes:**
- C-run2 and F-run2: start a **fresh Python process** with `state/` still populated from Run 1.
- Query G tests semantic recall: "credit assignment" appears in none of the 5 papers verbatim — the agent must reason from related concepts (backpropagation through reasoning, reward shaping, intermediate signals).

---

## Corpus — AI Engineering Patterns

**Application path:** Desktop app over curated documents  
**Item count:** 52 markdown files  
**File format:** Markdown  
**Location:** `corpus/`

**Rebuild command:**

```bash
python agent.py --index corpus/
```

### Corpus manifest (selected items)

| File | Topic |
|------|-------|
| `01_few_shot_prompting.md` | Few-shot example selection strategies |
| `09_context_window_management.md` | Sliding window truncation (75% threshold) |
| `10_artifact_serialization.md` | 4096-byte inline vs artifact threshold |
| `13_hybrid_search.md` | BM25 + dense embeddings with RRF |
| `18_semantic_near_duplicates.md` | Embedding collapse failure mode |
| `19_agent_loop_design.md` | Atomic decisions: one tool call per iteration |
| `40_catastrophic_forgetting_prevention.md` | Preserving base model capabilities during fine-tuning |
| … | (52 files total, all in corpus/) |

### New MCP tools added for corpus

| Tool | When to use |
|------|-------------|
| `index_document(path)` | When content must be searchable across turns. For one-shot reads use `read_file`. |
| `search_knowledge(query)` | When Memory already has indexed chunks for the topic. For fresh content use `fetch_url`. |

---

## Custom Queries (5 queries × 2 runs each)

Each query answers correctly **with** the indexed corpus and fails **without** it.

### Q1 — Artifact threshold (keyword recall)
**Query:** `Which of the indexed AI engineering documents recommends a specific byte threshold for deciding when to store responses as artifact handles rather than returning them inline?`  
**Answers with corpus:** `10_artifact_serialization.md` — 4096 bytes threshold  
**Fails without:** LLM guesses or says "I don't have that information"  
**Trace files:** `traces/custom/q1_with_corpus.json`, `traces/custom/q1_without_corpus.json`

### Q2 — Context management (keyword recall)
**Query:** `Which indexed document discusses what percentage of the context window triggers conversation history truncation, and what fraction gets removed?`  
**Answers with corpus:** `09_context_window_management.md` — 75% triggers truncation, remove oldest 30%  
**Fails without:** General answer without specific percentages  
**Trace files:** `traces/custom/q2_with_corpus.json`, `traces/custom/q2_without_corpus.json`

### Q3 — Hybrid search (semantic recall)
**Query:** `Which indexed pattern explains why relying solely on geometric similarity between vector representations is insufficient for production document retrieval?`  
**Note — semantic:** "geometric similarity between vector representations" does not appear in `13_hybrid_search.md`; the doc says "cosine similarity" and "dense embeddings". The vector path surfaces it correctly.  
**Grep check:** `grep -rEi "(geometric similarity|vector representations)" corpus/ | wc -l` → 0  
**Answers with corpus:** `13_hybrid_search.md`  
**Trace files:** `traces/custom/q3_with_corpus.json`, `traces/custom/q3_without_corpus.json`

### Q4 — Embedding collapse (semantic recall)
**Query:** `Which document warns about the specific pathology where a retrieval system returns chunks that share surface-level phrasing but carry entirely unrelated meaning?`  
**Note — semantic:** "surface-level phrasing" and "entirely unrelated meaning" do not appear in `18_semantic_near_duplicates.md`; the doc uses "embedding collapse" and "chunks that share common phrases".  
**Grep check:** `grep -rEi "(surface-level phrasing|entirely unrelated meaning)" corpus/ | wc -l` → 0  
**Answers with corpus:** `18_semantic_near_duplicates.md`  
**Trace files:** `traces/custom/q4_with_corpus.json`, `traces/custom/q4_without_corpus.json`

### Q5 — Atomic decisions (keyword recall)
**Query:** `Which indexed document gives a specific recommendation about how many tool calls an agent should make per decision step, and what failure mode does it cite as the reason?`  
**Answers with corpus:** `19_agent_loop_design.md` — exactly one tool call per iteration; partial failures cannot be retried cleanly  
**Fails without:** Generic answer or "I don't know"  
**Trace files:** `traces/custom/q5_with_corpus.json`, `traces/custom/q5_without_corpus.json`

---

## Semantic Recall Verification

Queries Q3 and Q4 are the two semantic-recall queries. Verifying the query words are absent from the corpus:

```bash
grep -rEi "(geometric similarity|vector representations)" corpus/ | wc -l
# expected: 0

grep -rEi "(surface-level phrasing|entirely unrelated meaning)" corpus/ | wc -l
# expected: 0
```

---

## Running Custom Queries — Workflow

```bash
# Without corpus (baseline failure)
rm -rf state/
python agent.py "Which of the indexed AI engineering documents recommends..." \
  --trace custom/q1_without_corpus.json

# Index corpus
python agent.py --index corpus/

# With corpus (should succeed)
python agent.py "Which of the indexed AI engineering documents recommends..." \
  --trace custom/q1_with_corpus.json
```

Repeat for Q2–Q5.

---

## Video

*(Link to be added after recording)*

3–5 minute demo covering:
1. Running Query Q3 (semantic recall) with and without corpus — showing the vector path retrieving the correct chunk
2. Tour of `viewer.html` — Architecture tab, Queries tab with iteration breakdown, Gateway tab with embed calls, Memory tab with FAISS stats

---

## Query Execution Logs

### Pass / Fail Summary

| Query | Run ID | Status | Verdict |
|---:|---|---|---|
| A — Claude Shannon | `29098454` | **SUCCESS** | Passed |
| B — Tokyo activities | `cc7f2872` | **SUCCESS** | Passed |
| C-run1 — Mom's birthday remember | `48e5786e` | **PARTIAL SUCCESS** | Not fully passed |
| C-run2 — Mom's birthday recall | `e07ff713` | **SUCCESS** | Passed |
| D — Python asyncio | `97f44bbc` | **PARTIAL SUCCESS** | Not fully passed |
| E — Index attention.md | `2d34d211` | **SUCCESS** | Passed |
| F-run1 — Index all papers | `cca2fcb0` | **SUCCESS** | Passed |
| G — Credit assignment | `112245d1` | **PARTIAL SUCCESS** | Not fully passed |
| H — ReAct vs CoT | `47acfa2f` | **PARTIAL SUCCESS** | Not fully passed |

### Custom Query Pass / Fail Summary

| Custom Query | Run ID | Status | Verdict | Reason |
|---:|---|---|---|---|
| 1 — Stale knowledge | `cc56c14c` | **PARTIAL SUCCESS** | Not fully passed | Answered mostly through CoT limitations, did not compare all indexed documents. |
| 2 — Teaching without retraining | `436d23f4` | **PARTIAL SUCCESS** | Not fully passed | Focused mainly on Chain-of-Thought; query asked for patterns plural. |
| 3 — Evaluation metrics | `da15fb6f` | **SUCCESS** | Passed | Identified documents and listed specific metrics (GSM8K accuracy, win rate, DPO loss). |
| 4 — Production RAG system order | `e8eb5251` | **PARTIAL SUCCESS** | Not fully passed | Gave useful order but did not sufficiently cover persistent memory and reliable evaluation. |

---

### Query A — Claude Shannon

**Query:** `Fetch https://en.wikipedia.org/wiki/Claude_Shannon and tell me his birth date, death date, and three key contributions to information theory.`  
**Run ID:** `29098454` | **Status:** SUCCESS | **Iterations:** 3 (bound: 3)

```
Iteration 1:
  Perception: [open] Fetch Wikipedia page | [open] Extract birth/death dates and contributions
  Decision:   TOOL_CALL: fetch_url({"url": "https://en.wikipedia.org/wiki/Claude_Shannon"})
  Action:     → [artifact art:505cff7a5b0297f3, 50336 bytes]

Iteration 2:
  Perception: [done] Fetch Wikipedia page | [open] Extract facts — attach=art:505cff7a5b0297f3
  Decision:   ANSWER: Birth Date: April 30, 1916 ...

Iteration 3:
  Perception: [done] Fetch Wikipedia page | [done] Extract facts
```

**Final answer:**
- **Birth Date:** April 30, 1916
- **Death Date:** February 24, 2001
- **Key Contributions:** (1) Founded Information Theory — 1948 paper "A Mathematical Theory of Communication"; (2) Entropy and the bit as fundamental unit of information; (3) Shannon-Hartley Theorem for maximum channel capacity.

---

### Query B — Tokyo Activities

**Query:** `Find 3 family-friendly things to do in Tokyo this weekend. Check Saturday's weather forecast there and tell me which one is most appropriate.`  
**Run ID:** `cc7f2872` | **Status:** SUCCESS | **Iterations:** 16 (bound: 8) — gateway 503 retries inflated count

```
Iteration 1:  web_search("top 3 tourist activities in Tokyo")
Iteration 2+: Repeated ANSWER attempts (gateway 503s caused retries)
Iteration 16: FINAL answer produced
```

**Final answer:**
1. Visit Tokyo Tower — sweeping city views from 333 m observation decks
2. Explore Senso-ji Temple in Asakusa — Kaminarimon gate, Nakamise shopping street, Japan's oldest Buddhist temple
3. Spend a day at Tokyo Disney Resort — Tokyo Disneyland or Tokyo DisneySea

---

### Query C-run1 — Mom's Birthday (Remember)

**Query:** `My mom's birthday is 15 May 2026. Remember that and create reminders for two weeks before and on the day.`  
**Run ID:** `48e5786e` | **Status:** PARTIAL SUCCESS | **Iterations:** 3 (bound: 4)

```
Iteration 1: create_file("2026-05-15_moms_birthday.txt")
Iteration 2: create_file("2026-05-01_reminder.txt")
Iteration 3: [done] all goals — final answer confirmed only one file
```

Note: Both files were created but the final answer only confirmed the second file, not both explicitly.

---

### Query C-run2 — Mom's Birthday (Recall)

**Query:** `When is mom's birthday?`  
**Run ID:** `e07ff713` | **Status:** SUCCESS | **Iterations:** 2 (bound: 3)

```
Iteration 1: read_file("2026-05-15_moms_birthday.txt")
Iteration 2: [done] — answered May 15, 2026
```

---

### Query D — Python asyncio Best Practices

**Query:** `Search for "Python asyncio best practices", read the top 3 results, and give me a short numbered list of the advice they agree on.`  
**Run ID:** `97f44bbc` | **Status:** PARTIAL SUCCESS | **Iterations:** 11 (bound: 6)

Fetched 3 URLs across 11 iterations with repeated answer attempts before perception marked "read top 3" done.

**Final answer:**
1. Always use `asyncio.run()` to start programs
2. Offload blocking code to a thread pool via `loop.run_in_executor()`
3. Use `async with` for async context managers

---

### Query E — Index attention.md

**Query:** `Index the file papers/attention.md and tell me what the three key contributions of the Transformer architecture are according to this paper.`  
**Run ID:** `2d34d211` | **Status:** SUCCESS | **Iterations:** 3 (bound: 5)

```
Iteration 1: index_document({"path": "papers/attention.md"})
Iteration 2: ANSWER: three key contributions
Iteration 3: [done] all goals
```

**Final answer:**
1. Pure self-attention architecture — no recurrence or convolution
2. Scaled dot-product attention — prevents softmax saturation at large magnitudes
3. Multi-head attention with positional encoding — parallel attention heads across representation subspaces

---

### Query F-run1 — Index All Papers

**Query:** `Index every .md file under papers/. Confirm how many chunks were indexed in total.`  
**Run ID:** `cca2fcb0` | **Status:** SUCCESS | **Iterations:** 8 (bound: 11)

```
Iteration 1: list_dir({"path": "papers/"}) → 5 files discovered
Iteration 2: index_document("papers/attention.md")
Iteration 3: index_document("papers/chain_of_thought.md")
Iteration 4: index_document("papers/dpo.md")
Iteration 5: index_document("papers/lora.md")
Iteration 6: index_document("papers/react.md")
Iteration 7: ANSWER: 13 chunks total
Iteration 8: [done] all goals
```

**Final answer:** 13 chunks — attention.md: 2, chain_of_thought.md: 2, dpo.md: 3, lora.md: 3, react.md: 3

---

### Query G — Credit Assignment

**Query:** `Across these papers, how do they handle the credit assignment problem?`  
**Run ID:** `112245d1` | **Status:** PARTIAL SUCCESS | **Iterations:** 6 (bound: 4)

Searched with `search_knowledge` twice before producing the final synthesis. Answer focused on CoT and ReAct; did not cover attention/DPO/LoRA aspects.

**Final answer summary:** CoT addresses credit assignment via intermediate natural language reasoning steps (makes failures interpretable); ReAct extends this with external action/observation feedback loops for mid-trajectory correction.

---

### Query H — ReAct vs Chain-of-Thought

**Query:** `Compare how the ReAct paper and the Chain-of-Thought paper differ in their treatment of intermediate reasoning.`  
**Run ID:** `47acfa2f` | **Status:** PARTIAL SUCCESS | **Iterations:** 10 (bound: 3)

Multiple `search_knowledge` calls (some returning empty) before final answer at iteration 9. Exceeded bound due to repeated search loop.

**Final answer summary:**
- **CoT:** Intermediate reasoning is purely internal — a "thought buffer" for logical decomposition before final output
- **ReAct:** Intermediate reasoning interleaved with external actions/observations — creates a grounding feedback loop; reasoning decides *which* action to take, then updates from results

---

### Custom Query 1 — Stale Knowledge

**Query:** `How do these documents address the stale knowledge problem?`  
**Run ID:** `cc56c14c` | **Status:** PARTIAL SUCCESS | **Iterations:** 3

Answer focused on CoT's structured reasoning as a mitigation; noted that CoT does not update knowledge but improves synthesis. Did not compare all 5 indexed documents.

---

### Custom Query 2 — Teaching Without Retraining

**Query:** `What strategies do these patterns recommend for teaching a model new behaviors without retraining?`  
**Run ID:** `436d23f4` | **Status:** PARTIAL SUCCESS | **Iterations:** 4

Answered with CoT strategies: (1) intermediate reasoning demonstrations, (2) problem decomposition, (3) few-shot with 8 human-annotated examples, (4) temperature=0 for reproducibility, (5) task-specific targeting, (6) leverage emergent capacity at 100B+ scale. Did not cover other papers (ReAct, LoRA, DPO).

---

### Custom Query 3 — Evaluation Metrics

**Query:** `Which of my indexed documents discuss evaluation metrics for LLM applications, and what specific metrics do they recommend?`  
**Run ID:** `da15fb6f` | **Status:** SUCCESS | **Iterations:** 6

**Final answer:**
- **Chain-of-Thought:** GSM8K (arithmetic), CommonsenseQA, StrategyQA, symbolic tasks (last-letter concatenation, coin flip)
- **DPO:** Preference classification — $L_{DPO}$ loss (log-sigmoid of log-likelihood ratio between policy and reference model on preferred vs non-preferred outputs)
- Performance comparison: accuracy % with vs without prompting technique

---

### Custom Query 4 — Production RAG System

**Query:** `Based on my indexed documents, if I wanted to build a production RAG system with persistent memory and reliable evaluation, which patterns should I combine and in what order?`  
**Run ID:** `e8eb5251` | **Status:** PARTIAL SUCCESS | **Iterations:** 3

**Recommended order from answer:**
1. Baseline Retrieval & Augmentation — foundational RAG pipeline
2. ReAct reasoning loop — think → search → reason through results
3. Chain-of-Thought in generation phase — step-by-step synthesis
4. DPO alignment — fine-tune on successful RAG interactions

Did not address persistent memory architecture or specific evaluation methodology.
