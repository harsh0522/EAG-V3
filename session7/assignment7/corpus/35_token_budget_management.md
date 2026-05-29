# Token Budget Management

## Problem Statement

Token costs accumulate across input tokens, output tokens, cached tokens, and embedding tokens. Without explicit budget tracking per request, per feature, and per time period, cost anomalies — a single user triggering 10,000 requests in an hour, or a pipeline generating unexpectedly long outputs — go undetected until the monthly invoice arrives.

## Solution / Pattern

Implement a token budget manager as a middleware layer that intercepts every API call, records token counts from the response metadata, and enforces budget limits. The budget manager should track usage across three dimensions: per-user limits (prevent individual users from consuming disproportionate resources), per-feature limits (prevent runaway pipelines), and total service limits (prevent billing surprises).

When a limit is approached (above 80% consumed), the budget manager should reduce the output token limit for that user or feature to extend service within the remaining budget. When a limit is reached, it should serve a graceful degradation response rather than a hard error.

## Key Details

- Set input token limits conservatively: a single request with a 32,000-token context costs as much as 32 requests with 1,000-token contexts; anomalously large inputs should trigger review.
- Track token usage in a time-series database (e.g., InfluxDB, Prometheus) with 1-minute resolution to detect spikes in real time rather than in batch summaries.
- The maximum output token limit should be set to 2x the expected output length for the task type; setting it to the model maximum wastes money on tasks with bounded outputs (a classification task does not need 4,096 output tokens).
- Implement token budgets as a Redis sorted set keyed by user/feature ID with TTL-based rolling windows; this allows efficient sliding-window rate limiting without persistent storage requirements.
- Alert when any single request consumes more than 10% of the daily budget for a single feature; this is a strong signal of a prompt engineering bug or a data-driven runaway loop.
- Reconcile tracked token counts against provider invoices monthly; discrepancies above 5% indicate a tracking gap — requests being made outside the budget manager's middleware.
