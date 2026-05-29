# Rate Limit Handling

## Problem Statement

LLM API providers enforce rate limits on requests per minute (RPM), tokens per minute (TPM), and sometimes concurrent requests. Applications that do not handle rate limits gracefully fail with errors during traffic spikes, create poor user experiences, and may trigger account-level restrictions from repeated limit violations.

## Solution / Pattern

Rate limit handling requires three complementary mechanisms: proactive throttling (staying below the limit), reactive retry (handling 429 errors with exponential backoff), and priority queuing (ensuring high-priority requests succeed even when the request queue backs up).

Implement a token bucket rate limiter at the application layer that tracks your current RPM and TPM consumption and preemptively queues requests when approaching the limit rather than sending them and receiving 429 responses.

## Key Details

- Target 80% of your allocated rate limit as the operating threshold; keeping 20% headroom prevents burst traffic from causing limit violations while the rate limiter adjusts.
- Exponential backoff parameters for 429 retry: first retry after 1 second, second after 4 seconds, third after 16 seconds, fourth after 64 seconds, then fail after 4 retries. Do not retry indefinitely; after 4 retries, return an error and let the orchestrating system decide.
- Track TPM (tokens per minute) separately from RPM; a large-context request can consume an entire minute's token budget in a single call, blocking all other requests. Implement per-request token budget checks before submission.
- Use the `retry-after` header value from 429 responses when present; providers set this to the minimum wait time to clear the limit, and using it is more efficient than fixed backoff.
- For batch processing pipelines, implement a token-aware request scheduler that packs requests to maximize TPM utilization without exceeding the limit; this can increase throughput by 30–50% compared to fixed-rate submission.
- Monitor your limit utilization in real time with 10-second resolution; spikes that are invisible at 1-minute granularity cause the most limit violations.
