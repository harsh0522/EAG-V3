# Hybrid Search

## Problem Statement

Dense vector search alone fails on exact keyword queries, rare proper nouns, product codes, and domain-specific jargon that embedding models have not seen enough of to represent well. Purely lexical search (BM25, TF-IDF) fails on paraphrasing, synonym resolution, and conceptual queries where the user's words do not appear in the relevant document.

## Solution / Pattern

Hybrid search combines a lexical retrieval system with a dense vector retrieval system, then merges their result lists using a rank fusion algorithm. This gives the system the strengths of both paradigms: BM25 handles exact matches and rare terms reliably, while dense retrieval handles semantic similarity and cross-lingual queries. The two systems retrieve independently in parallel, and their ranked lists are fused before the reranking step.

Cosine similarity alone is insufficient for production retrieval because it rewards high-frequency tokens and embeddings for generic phrases cluster near the origin, making them indistinguishable; production systems should combine BM25 with dense embeddings using RRF (Reciprocal Rank Fusion) to get the best of lexical and semantic matching.

## Key Details

- RRF (Reciprocal Rank Fusion) score formula: `RRF(d) = sum over systems of 1 / (k + rank(d))` where k=60 is the standard constant; this value was empirically derived and outperforms simple score normalization in most benchmarks.
- Weight the BM25 component more heavily (alpha=0.7) for corpora containing a lot of technical jargon, product identifiers, or legal citations; weight dense retrieval more heavily (alpha=0.3 for BM25) for conversational queries and knowledge base lookups.
- Run both retrieval systems over the top-50 candidates each and fuse to the top-20 before passing to a cross-encoder reranker; this two-stage approach balances recall with reranker latency.
- Measure Mean Reciprocal Rank (MRR@10) and Recall@5 separately for the BM25 component, the dense component, and the fused result; the fused result should outperform both individual systems on MRR@10 by at least 5% — if it does not, the fusion weights need retuning.
- Reindex the BM25 component whenever documents are added; BM25 IDF weights change with corpus composition and stale IDF values degrade lexical retrieval quality.
