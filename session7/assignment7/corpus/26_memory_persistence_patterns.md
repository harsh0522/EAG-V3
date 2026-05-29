# Memory Persistence Patterns

## Problem Statement

In-context memory is ephemeral; it disappears when the session ends. Systems that rely exclusively on in-context memory cannot improve with usage, cannot personalize across sessions, and cannot recover from session interruptions. Persisting the right information at the right time is a core engineering challenge in production agent systems.

## Solution / Pattern

Memory persistence requires an explicit write policy that specifies what triggers a write, what content is written, and where it is stored. Use an event-driven write policy: trigger writes at session completion, at goal achievement milestones within a session, and when the agent explicitly learns a new fact or preference from user feedback.

For each persistence event, extract a structured memory record containing: the trigger event type, a summary of what was learned, a confidence score, metadata (timestamp, session ID, source), and a vector embedding of the summary for future retrieval. Store records in a vector store for semantic retrieval and optionally in a relational database for structured queries.

## Key Details

- Write session summaries within 60 seconds of session completion; delayed writes create gaps in the memory timeline if the system restarts between session end and write completion.
- Apply deduplication before each memory write: embed the new memory candidate and check its cosine similarity against the 5 most recent memory entries; if similarity exceeds 0.92, update the existing entry rather than creating a new one.
- Store memory records with an explicit `confidence` float between 0.0 and 1.0; only retrieve memories with confidence above 0.7 for injection into production sessions; lower-confidence memories can be retained for analysis but should not influence agent behavior.
- Implement a memory audit log (append-only) separate from the memory store itself; the audit log records every write, update, and delete operation with the reason, enabling rollback and forensic investigation when the agent develops incorrect beliefs.
- Test memory persistence under session interruption: simulate process crashes at random points in a session and verify that persisted memory reflects only committed writes.
