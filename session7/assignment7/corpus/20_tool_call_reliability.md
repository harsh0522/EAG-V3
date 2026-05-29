# Tool Call Reliability

## Problem Statement

Tool calls are the primary vector through which agents take real-world actions. Unreliable tool invocation — malformed arguments, missing required fields, invalid enum values — causes agent workflows to fail partway through multi-step tasks, often leaving external systems in inconsistent states.

## Solution / Pattern

Tool call reliability requires validation at three stages: before sending the call to the tool, after receiving the result, and as part of the agent's next reasoning step. Before execution, validate all tool arguments against the tool's schema using the same library that validates user input. Reject calls with invalid arguments immediately and return a structured error to the model so it can self-correct rather than executing a bad call that may be non-idempotent.

After execution, validate that the tool's return value matches the expected schema. If the tool returns an error, classify it as retryable (rate limit, temporary network failure) or terminal (invalid credentials, resource not found) and handle accordingly. Feed the full result, including error details, back into the agent's context for the next reasoning step.

## Key Details

- Use JSON Schema validation on all tool arguments before dispatch; this catches approximately 85% of argument errors before they cause side effects in external systems.
- Implement per-tool retry logic with exponential backoff: first retry after 1 second, second retry after 4 seconds, third retry after 16 seconds, then fail; do not retry terminal errors (4xx HTTP status codes other than 429).
- Log every tool call with its arguments, result, latency, and success/failure status; this structured log is the primary debugging artifact for investigating agent failures in production.
- Define a maximum argument size for each tool to prevent accidental injection of large documents as tool arguments; a practical limit is 8,192 tokens per argument value.
- For tools with side effects (write, delete, send), require explicit confirmation from the agent in a structured field within the tool call (e.g., `"confirmed": true`) to prevent accidental execution from hallucinated calls.
- Instrument tool success rate as a per-tool metric in production; a drop in success rate for a specific tool is the earliest indicator of schema drift or downstream API changes.
