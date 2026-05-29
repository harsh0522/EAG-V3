# Streaming Responses

## Problem Statement

Non-streaming responses require the model to complete full generation before any output is delivered to the user. For responses longer than a few sentences, this creates multi-second waits that significantly degrade perceived responsiveness, especially in interactive chat applications where users expect fast feedback.

## Solution / Pattern

Streaming delivers tokens to the client as they are generated, reducing time-to-first-token from the full generation latency to the first-token latency (typically 200–600ms for most providers). Implement streaming using server-sent events (SSE) for web applications or a streaming gRPC connection for service-to-service communication.

On the client side, render streaming tokens progressively. Implement a token buffer that accumulates tokens into meaningful display units (sentences or phrases) before rendering, rather than rendering each token individually, to prevent UI jitter from single-character updates.

## Key Details

- Buffer streaming tokens into chunks of 5–10 words before rendering in UI; rendering at the token level causes visible flickering in most web interfaces and degrades perceived quality.
- For downstream systems that require complete outputs (databases, structured parsers), assemble the full stream before processing; do not attempt to parse partial JSON or partial structured output from a stream.
- Implement stream timeout handling: if no token is received within 30 seconds during generation, the connection has stalled — cancel the request and retry or surface an error. Do not wait indefinitely.
- Time-to-first-token (TTFT) and tokens-per-second (TPS) are the two key streaming performance metrics; TTFT drives perceived responsiveness, TPS drives reading experience for long outputs.
- Stream interruption (user navigates away, network drop) should cancel the generation request at the provider, not just disconnect the client; uncancelled server-side generation wastes tokens and counts against your rate limit.
- Apply output validation only to the complete assembled stream, not to intermediate chunks; partial outputs are almost always invalid from a format perspective and will always fail schema validation.
