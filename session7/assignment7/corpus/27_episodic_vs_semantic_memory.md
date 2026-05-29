# Episodic vs. Semantic Memory

## Problem Statement

Developers building agent memory systems often store all memory in a single undifferentiated vector store. This conflates event-specific memories (what happened in session 47 on Tuesday) with general knowledge (the user prefers concise responses), causing retrieval to mix the two and produce irrelevant injections.

## Solution / Pattern

Episodic memory stores records of specific events and interactions: what happened, when, and in what context. Semantic memory stores distilled, timeless knowledge extracted from events: facts, preferences, and learned domain knowledge that remain valid across sessions. These two memory types have different retrieval strategies, different update frequencies, and different retention policies, so they must be stored in separate indices.

Episodic retrieval is typically triggered by task similarity: "have I done something like this before?" Semantic retrieval is triggered by knowledge need: "what do I know about this topic or user?" Use different query formation strategies for each.

## Key Details

- Episodic memories should include: session ID, task goal, outcome (success/failure), key decision points, and a 100-150 token narrative summary. This structure supports both similarity-based retrieval and structured query filtering (e.g., "retrieve successful sessions involving the topic X from the past 30 days").
- Semantic memories should be stored as atomic fact units: one claim per record, with source citation and confidence score. Multi-fact records are harder to update when one fact changes and are retrieved with lower precision.
- Update semantic memory on a scheduled basis (e.g., nightly) rather than during sessions; batch extraction of semantic facts from the day's episodic events is more accurate than incremental extraction and avoids latency impact.
- Retention policy: keep all episodic memories for 90 days, then archive to cold storage; keep semantic memories indefinitely but mark them as "stale" after 6 months without a corroborating update.
- Inject a maximum of 2 episodic memories and 5 semantic facts into any single session prompt; beyond this, the injected memory overhead exceeds its marginal benefit on task performance.
