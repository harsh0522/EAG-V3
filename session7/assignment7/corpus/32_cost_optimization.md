# Cost Optimization

## Problem Statement

LLM inference costs can scale faster than revenue in production AI applications. Without explicit cost management, a pipeline that costs $1,000/month at 10,000 daily active users may cost $50,000/month at 100,000 users — a linear scaling that makes unit economics unsustainable.

## Solution / Pattern

Cost optimization operates at five levels: prompt efficiency, model selection, caching, batching, and architecture. Address them in this order, as earlier levels offer more leverage for less implementation complexity. Prompt efficiency — removing redundant instructions, compressing retrieved context, reducing few-shot example count — typically reduces costs by 20–40% with no quality degradation. Model selection (routing simple tasks to cheaper models) reduces costs by 30–60%. Caching identical or near-identical requests eliminates cost entirely for repeated queries.

Track cost per feature, not just total cost; knowing that the summarization feature costs $0.003 per call versus $0.0008 for the classification feature enables targeted optimization efforts.

## Key Details

- Implement semantic caching for requests: embed the incoming query and check cosine similarity against a cache of recent query embeddings; a similarity above 0.97 allows serving the cached response. This typically achieves a 15–25% cache hit rate in conversational applications.
- Prompt caching (available from major providers) caches the processed key-value representation of static prompt prefixes; activate this for any prompt component that does not change between requests — system prompts, few-shot examples, large reference documents.
- Batch non-real-time requests (background summaries, document processing, nightly reports) and send them via batch API endpoints where available; batch pricing is typically 50% lower than synchronous endpoint pricing.
- Set per-user, per-session, and per-feature daily cost budgets enforced at the application layer; users or sessions that exceed budget should degrade gracefully (e.g., route to cheaper model) rather than fail.
- Review cost per token-output versus cost per token-input; output tokens cost 3–5x more than input tokens on most provider pricing schedules, making verbose output more costly than verbose prompts.
