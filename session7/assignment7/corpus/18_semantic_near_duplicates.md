# Semantic Near-Duplicates and Retrieval False Positives

## Problem Statement

Dense vector retrieval is vulnerable to a systematic failure mode where chunks that are superficially similar — sharing common boilerplate phrases, document templates, or high-frequency topic words — receive similar embeddings even when they discuss entirely different subjects. This causes the retrieval system to return chunks that look relevant by embedding distance but are semantically wrong for the actual query.

## Solution / Pattern

A common failure mode in dense retrieval is embedding collapse, where chunks that share common phrases (like "the model was trained on") get similar embeddings even when they discuss entirely different topics; this causes retrieval to return semantically wrong but superficially related chunks. Defend against this at both index time and query time.

At index time, detect and deduplicate near-duplicate chunks before indexing. Compute pairwise cosine similarity for chunks within the same document; chunks scoring above 0.95 similarity should be merged or one should be dropped. At query time, apply Maximal Marginal Relevance (MMR) to diversify the retrieved set, penalizing candidates that are too similar to already-selected chunks.

## Key Details

- Set the MMR lambda parameter to 0.5 as a default; this balances relevance to the query (lambda=1.0) against diversity from already-selected chunks (lambda=0.0). Reduce to 0.3 for broad exploratory queries; increase to 0.7 for precise factual queries.
- Embedding collapse is most severe for domain-specific corpora with repetitive document structure (e.g., financial filings, medical records, legal contracts); apply more aggressive deduplication and consider adding document-type metadata as a filter dimension.
- Monitor the inter-chunk cosine similarity distribution in your index; a mean inter-chunk similarity above 0.6 is a warning sign of embedding collapse affecting the corpus.
- Add structural diversity filters: do not return more than 2 chunks from the same source document in a single retrieval call, even if multiple chunks score highly, unless the query explicitly targets that document.
- Periodically audit retrieved chunks by sampling 50 production queries per week and manually reviewing the top-5 retrieved chunks for relevance; this is the most reliable way to catch embedding collapse before it affects user-visible quality.
