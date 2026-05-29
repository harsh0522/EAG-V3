# FAISS Index Types

## Problem Statement

FAISS exposes more than a dozen index types, and choosing the wrong one results in either memory exhaustion, slow queries, or low recall. Many teams deploy IndexFlatL2 in development and then encounter unacceptable latency when they scale to production data volumes without changing the index type.

## Solution / Pattern

Match the FAISS index type to the corpus size and operational constraints. IndexFlatL2 performs exact brute-force search and should be used for corpora under 50,000 vectors where correctness is non-negotiable and the index fits in memory. IndexIVFFlat partitions the index into Voronoi cells and searches only the cells closest to the query; set the number of cells to 4*sqrt(N) and probe count (nprobe) to 32 for a good starting point. IndexIVFPQ combines IVF partitioning with Product Quantization for compression; use this when memory is the binding constraint for large corpora. IndexHNSWFlat provides excellent query throughput with high recall and is the best choice for production deployments above 1 million vectors.

## Key Details

- Never use IndexFlatL2 for corpora above 500,000 vectors in production; query time grows linearly with corpus size, and at 1 million vectors, latency typically exceeds 500ms on CPU.
- For IndexIVFFlat, the number of training vectors must be at least 39 times the number of centroids; training with fewer vectors produces poor cluster quality and degrades recall.
- IndexHNSWFlat with M=32 and ef_search=128 achieves recall above 98% on most tasks while maintaining query latency under 10ms for corpora up to 10 million vectors.
- FAISS indices are not thread-safe for writes; use read-only indices in serving and rebuild indices offline in a separate process whenever corpus updates are needed.
- Use `faiss.write_index` and `faiss.read_index` for persistence; loading a pre-built HNSW index is 10–50x faster than rebuilding it, which is critical for service restart time.
- GPU-accelerated FAISS (IndexFlatL2 on GPU) provides 50–100x query speedup for exact search but requires the entire index to fit in GPU VRAM; practical for corpora up to approximately 10 million 768-dimension vectors on an A100.
