# Caching Strategies

## Problem Statement

LLM inference is computationally expensive. Many production applications receive repeated or highly similar requests — the same FAQ question from different users, the same document processed multiple times with different queries. Without caching, every request incurs full inference cost even when the output is identical to a previous computation.

## Solution / Pattern

Deploy three layers of caching: exact match caching, semantic caching, and prompt prefix caching. Exact match caching stores request-response pairs keyed by a hash of the full request (system prompt + user message + parameters); hit rate is typically 5–15% for conversational applications, higher for FAQ-style systems. Semantic caching stores embeddings of past queries and serves cached responses when a new query embedding is within a threshold distance of a cached query. Prompt prefix caching stores processed key-value (KV) representations of shared prompt prefixes on the provider side.

## Key Details

- Semantic cache hit threshold: serve a cached response when cosine similarity exceeds 0.97 between the incoming query embedding and a cached query. Below 0.97, semantic differences are significant enough that the cached response may not address the new query correctly.
- Semantic cache lookup adds approximately 5–10ms for index search; this is negligible compared to inference latency but should be measured and monitored to ensure the cache lookup itself doesn't become a bottleneck.
- Prompt prefix caching requires that the cached prefix is at least 1,024 tokens for most providers to achieve meaningful savings; shorter prefixes may not meet the minimum cacheable length threshold.
- Cache invalidation for semantic caches: when the underlying documents or knowledge base changes, embed the changed content and invalidate all cached responses whose source embeddings are within 0.90 cosine similarity of the changed content.
- Set TTL (time-to-live) for cached responses based on content volatility: 24 hours for stable knowledge-base content, 1 hour for news or current events content, no caching for requests that reference the current time or date.
- Track cache hit rate, byte size of cached responses, and cost savings per day as operational metrics; a declining hit rate signals that request diversity is increasing and caching strategy needs revision.
