# Working Memory Limits

## Problem Statement

LLM context windows, while large, are finite. As agent sessions accumulate tool results, retrieved memories, retrieved documents, and conversation history, the prompt grows to consume the entire context window. At this point, either the model truncates input silently or the API returns an error, causing agent failure mid-task.

## Solution / Pattern

Treat the context window as a managed resource with an explicit budget allocator. Before each model call, compute the exact token count of each context component (system prompt, memory injections, retrieved documents, conversation history, tool results) and enforce pre-defined budget limits per component. When a component exceeds its budget, compress or truncate it before the call rather than after the limit is hit.

Define component budgets as percentages of the total window: system prompt 10%, memory injections 10%, retrieved documents 25%, conversation history 35%, tool results 15%, output headroom 5%. These percentages are a starting point and should be tuned based on your task distribution.

## Key Details

- Always count tokens before the API call, not after; post-call truncation is not possible. Use the model provider's tokenizer library (tiktoken for OpenAI, transformers tokenizer for open models) for accurate counts.
- Set the output headroom to at least 1,024 tokens regardless of context window size; models that run out of output tokens mid-sentence produce incomplete responses that are difficult to handle gracefully.
- When conversation history exceeds its budget, summarize older turns rather than deleting them; deletion breaks conversational coherence, while summarization maintains the semantic thread.
- Implement a "context pressure" metric: tokens used divided by maximum context. When pressure exceeds 0.85, log a warning and trigger more aggressive compression. When it exceeds 0.95, halt and fail gracefully rather than risk a truncation error.
- Use streaming token counts during multi-turn sessions rather than recomputing from scratch each turn; incremental counting reduces per-turn overhead from O(total_tokens) to O(new_tokens).
