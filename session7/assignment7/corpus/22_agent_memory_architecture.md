# Agent Memory Architecture

## Problem Statement

Agents with only in-context memory cannot learn from past interactions, cannot recall decisions made in previous sessions, and cannot share knowledge across multiple agent instances running in parallel. This limits the utility of agents to single-session tasks and prevents the accumulation of institutional knowledge.

## Solution / Pattern

Agent memory should be organized into four tiers with different access characteristics. Working memory holds the current conversation context and is discarded at session end. Episodic memory stores summaries of completed sessions indexed by timestamp and session goal, retrieved by semantic similarity when a new session starts with a related goal. Semantic memory holds extracted facts, user preferences, and learned domain knowledge in a structured knowledge base. Procedural memory encodes reusable workflows and decision rules learned from successful past task completions.

Each tier requires separate storage infrastructure and retrieval mechanisms. Working memory lives in the prompt. Episodic and semantic memories are stored in a vector database. Procedural memories are best stored as structured templates in a document store.

## Key Details

- At session start, inject at most 3 retrieved episodic memories into the system prompt to avoid overwhelming the context with past context; prioritize memories with high similarity to the current goal and recency within the past 30 days.
- Episodic memory summaries should be 100–150 tokens each; shorter summaries lose important detail, longer ones consume excessive context budget across multiple injected memories.
- Write semantic memory updates asynchronously after session completion, not during the session; in-session memory writes add latency to every turn and risk writing premature conclusions.
- Implement a confidence threshold for semantic memory updates: only store facts extracted with model confidence above 0.85 to prevent the memory tier from accumulating hallucinated "facts."
- Purge episodic memories older than 90 days that have never been retrieved; stale memories waste storage and add retrieval noise without providing value.
