# Vector Index Selection

## Problem Statement

Choosing the wrong vector index type leads to either unacceptable query latency, excessive memory consumption, or poor recall at scale. A flat exact search index that works well at 10,000 vectors becomes unusable at 10 million vectors, but switching index types at scale requires re-indexing all vectors.

## Solution / Pattern

Vector index selection depends on three primary variables: corpus size, memory budget, and acceptable recall trade-off. For corpora under 100,000 vectors, a flat FAISS index (IndexFlatL2 or IndexFlatIP) provides exact nearest neighbor search with no recall loss and is fast enough for production latency requirements at this scale. For corpora from 100,000 to 5 million vectors, IVF (Inverted File Index) with 4*sqrt(N) centroids and a probe count of 32–64 delivers a good recall-speed trade-off. For corpora above 5 million vectors, HNSW (Hierarchical Navigable Small World) with M=32 and ef_construction=200 provides the best query throughput with manageable memory overhead.

## Key Details

- IVF index recall degrades significantly if the number of probes is too low; always measure recall at your target k before deploying an IVF index, and increase nprobe until recall exceeds 90%.
- HNSW uses approximately 1.1 * (M * 8 bytes) per vector in memory; at M=32, a 1-million-vector index requires roughly 280MB of RAM just for the graph structure, before accounting for stored vectors.
- Quantization (PQ, SQ8) can reduce memory by 4–8x at the cost of 2–5% recall degradation; acceptable for large corpora but not recommended when corpus quality is variable and precision matters.
- Build the index offline and load it read-only at serving time; dynamic insertion is slow and degrades index quality for IVF and HNSW until the index is rebuilt.
- Re-index corpora whenever the number of documents grows by more than 25% since the last index build; index quality metrics (recall, latency P95) should be tracked as regression tests.
