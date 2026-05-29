# Context Window Management

## Problem Statement

Long-running conversations and multi-step agentic tasks accumulate conversation history that eventually exceeds the model's context window. Naive truncation from the top discards the system prompt and early instructions; naive truncation from the bottom discards the most recent user message. Both approaches break the agent's ability to function correctly.

## Solution / Pattern

Context window management requires a proactive strategy that monitors token usage continuously and applies structured compression before the window is full. The sliding window approach keeps the system prompt, the most recent N turns, and a compressed summary of earlier turns. When context exceeds 75% of the window, truncate the oldest 30% of conversation history to prevent context overflow, then replace the removed turns with a model-generated summary of their content.

This summary-and-slide approach preserves the semantic thread of the conversation while keeping token counts within safe limits. The summary itself should be generated with a dedicated call at temperature 0.0 and stored separately from the live conversation buffer for audit purposes.

## Key Details

- Trigger the compression step at 75% window utilization, not at 100%; waiting until the window is full forces an emergency truncation that may cut mid-sentence or mid-tool-call.
- When removing conversation turns, always remove complete turn pairs (user + assistant) rather than partial turns; partial turns confuse the model about who produced which content.
- The compression summary should be prepended to the remaining conversation with an explicit label: "Summary of earlier conversation:" — without this label, models sometimes interpret the summary as a user message.
- Reserve a fixed headroom of at least 1,024 tokens for the model's output; if available context minus current prompt tokens falls below 1,024, force compression before the next inference call.
- Track context utilization as a production metric; a sustained average above 70% indicates your pipeline needs either more aggressive compression or a model with a larger context window.
- For agents that run for more than 20 turns on average, implement a memory tier that stores compressed episode summaries persistently and injects only the most relevant summary into fresh sessions.
