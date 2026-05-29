# Latency vs. Accuracy

## Problem Statement

Every technique that improves generation accuracy — larger models, more retrieved chunks, reranking, chain-of-thought, multi-step validation — adds latency. Production systems must make explicit trade-offs rather than treating accuracy as the sole optimization target.

## Solution / Pattern

Map your application's latency budget to a techniques menu. Identify the user-facing latency budget first (e.g., 2 seconds for a search answer, 30 seconds for a detailed report) and then select techniques that fit within it. Streaming responses to the user reduce perceived latency significantly for long outputs; the time-to-first-token (TTFT) matters more to user experience than total response time for interactive applications.

Profile each pipeline stage separately (embedding lookup, vector search, reranking, generation) to identify where latency is concentrated before optimizing. In most RAG pipelines, generation accounts for 60–80% of total latency; retrieval and reranking account for the remaining 20–40%.

## Key Details

- Time-to-first-token should be under 800ms for interactive applications; users perceive responses beginning within 800ms as instantaneous, while responses beginning after 1.5 seconds feel slow regardless of total generation quality.
- Reranking with a cross-encoder adds 50–200ms; this is almost always worth the accuracy trade-off for non-streaming use cases where total latency is under 5 seconds.
- For latency-critical applications, use a smaller embedding model (e.g., 100M parameter model rather than 600M) for real-time queries; the recall loss from smaller embedding models is typically under 3% and the latency saving is 4–6x.
- Parallel retrieval (querying the vector index and BM25 index simultaneously rather than sequentially) saves 40–80ms in hybrid search pipelines — a significant fraction of the retrieval budget.
- Cache embedding computations for repeated queries using a Redis store keyed by query hash; at high request volume, re-embedding the same query on every call is a significant wasted cost and latency.
- Measure and report P50, P90, and P99 latency separately; P99 latency is often 3–5x P50 due to tail behavior from large documents, cache misses, or model loading delays.
