# Tool Result Handling

## Problem Statement

Raw tool results are often not in a format that maximizes the model's comprehension or minimizes token usage. Tool results can be excessively long, contain irrelevant fields, or arrive in formats (HTML, binary, raw JSON) that the model handles poorly. Injecting unprocessed results into context wastes tokens and degrades reasoning quality.

## Solution / Pattern

Implement a result transformation layer between tool execution and context injection. This layer performs three operations: filtering (removing fields irrelevant to the current task), formatting (converting HTML to plain text, binary to a description, nested JSON to a flattened structure), and truncation (capping result length at a configured token limit with a clear indication of truncation).

Design this transformation layer as a modular pipeline where each tool has a registered result formatter. Generic fallback formatting should be applied when no tool-specific formatter is registered, ensuring no raw tool output ever reaches the model unprocessed.

## Key Details

- Set a per-tool maximum result size of 2,048 tokens; results exceeding this should be stored as artifacts and replaced with a handle plus a 3-sentence summary injected into context.
- Convert all HTML results to markdown before injection; markdown is significantly more token-efficient than HTML and preserves structure (headings, lists, links) in a model-readable format.
- For JSON results, flatten nested structures more than 2 levels deep and remove null fields, empty arrays, and metadata fields (internal IDs, timestamps) unless the task requires them.
- Implement result validation: if a tool's formatted result contains fewer than 20 tokens, it is likely an empty or error response; log a warning and include the raw result alongside the formatted version so the model can parse the actual error.
- Track tool result size distribution in production; tools whose p90 result size consistently exceeds 1,500 tokens are candidates for server-side pagination or more aggressive filtering.
- Include a "result source" header in the injected context (e.g., "Result from: database_query tool, invoked at step 4") to help the model track provenance when multiple tool results are present in the same context.
