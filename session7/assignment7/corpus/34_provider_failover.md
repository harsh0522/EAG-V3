# Provider Failover

## Problem Statement

LLM API providers experience outages, rate limit enforcement, and latency spikes that can make them temporarily unavailable. Applications that depend on a single provider have no recourse during outages and must either serve errors or degrade severely.

## Solution / Pattern

Implement a multi-provider failover strategy with a primary provider, at least one secondary provider, and a degraded-mode fallback. Route all requests to the primary provider under normal conditions. When the primary provider returns an error (5xx) or exceeds a latency threshold, automatically route to the secondary. If both fail, serve a degraded response from a local or cached model.

Use a circuit breaker pattern: after 5 consecutive failures from a provider within a 60-second window, open the circuit breaker and route all traffic to the secondary for 5 minutes before attempting to close the circuit with a single test request.

## Key Details

- Failover latency (the time from detecting primary failure to routing to secondary) should be under 500ms; longer failover windows result in user-visible errors or timeouts.
- Maintain API clients and authentication for all providers in a pre-warmed state; lazy initialization of the secondary client adds unnecessary latency during failover events.
- Normalize provider-specific error codes and response formats in an abstraction layer; failover logic should not need to know which provider is active, only that it has an available provider.
- Test failover quarterly by intentionally directing all traffic to the secondary and measuring accuracy and latency degradation; secondary providers should achieve at least 90% of primary provider quality on your evaluation set.
- Log all failover events with the triggering error code, failover duration, and number of requests affected; this log is critical for SLA reporting and for identifying providers with reliability patterns.
- Negotiate separate rate limit quotas on each provider; a failover to a provider where you share a quota with your primary traffic is not true failover and will exhaust secondary quota rapidly.
