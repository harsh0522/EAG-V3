# Memory Retrieval Strategies

## Problem Statement

A memory store that accumulates thousands of records without an effective retrieval strategy becomes a liability. Injecting the wrong memories misleads the agent; missing relevant memories causes it to repeat mistakes or ignore established user preferences.

## Solution / Pattern

Effective memory retrieval combines semantic similarity search with structured metadata filtering. Semantic search finds memories topically related to the current task; metadata filters restrict the search to memories of the right type, recency, and confidence level. Neither alone is sufficient: semantic-only search retrieves old, superseded memories with high similarity; filter-only search misses memories with different surface forms but identical meaning.

Implement a two-stage retrieval process: first apply metadata filters to reduce the candidate set (e.g., only memories with confidence > 0.7 and age < 30 days), then run semantic search over the filtered set. This is more precise and faster than searching the full memory store with semantic similarity alone.

## Key Details

- Separate the query used for memory retrieval from the literal user input; reformulate the query to focus on the knowledge need: "What do I know about [topic/entity]?" rather than using the raw user sentence, which may contain irrelevant context.
- Retrieve 10 candidate memories and inject only the top 3 after reranking by a combined score of similarity (70% weight) and recency (30% weight); this prevents the injection of high-similarity but outdated memories.
- For preference memories (user likes/dislikes), always retrieve regardless of similarity score if the topic overlaps with the current task; user preferences are often expressed in very different words than the tasks they apply to.
- After injection, include a metadata line with each injected memory: "(Memory: confidence=0.87, recorded 12 days ago)" — this allows the model to weight more recent and confident memories appropriately.
- Monitor memory retrieval hit rates; if more than 40% of sessions have no relevant memories retrieved, the memory store is not accumulating useful knowledge and the write policy needs review.
