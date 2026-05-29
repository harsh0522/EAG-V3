# Reranking Pipeline

## Problem Statement

First-stage retrieval (vector search or BM25) optimizes for recall — getting the right document somewhere in the top-k results. But it does not optimize for rank — ensuring the most relevant document is at position 1. Downstream models attending to the full retrieved set are sensitive to position ordering; relevant content buried at position 8 of 10 contributes less than content at position 1.

## Solution / Pattern

A reranking pipeline adds a second stage that rescores a large candidate set (top-20 to top-100) from first-stage retrieval using a cross-encoder model. Cross-encoders process the query and a candidate chunk jointly — not independently as in the bi-encoder embedding phase — allowing them to model fine-grained query-document interactions. The cross-encoder outputs a relevance score, and the candidates are resorted by this score to produce a smaller, higher-quality set (top-3 to top-5) for the generation stage.

## Key Details

- Cross-encoder reranking adds 50–200ms of latency depending on model size and candidate set size; use a small cross-encoder (100M–300M parameters) rather than a large LLM for reranking to keep P95 latency under 300ms.
- Rerank the top-20 candidates from first-stage retrieval rather than the full corpus; reranking more than 20 candidates with a cross-encoder is rarely cost-effective relative to the recall improvement.
- Calibrate the cross-encoder's score threshold; chunks scoring below 0.4 (on a 0–1 scale) should be dropped from the prompt even if they are in the top-k, because below this threshold the content is more likely to confuse than help the generator.
- For latency-sensitive pipelines, run the reranker asynchronously while a lightweight preview of top-3 vector results is displayed to the user; swap in the reranked results when they become available.
- Evaluate reranker performance with NDCG@5 (Normalized Discounted Cumulative Gain); a good reranker should improve NDCG@5 by at least 10 percentage points over the first-stage ranking.
- Fine-tune the reranker on domain-specific relevance labels if the out-of-box model does not reach NDCG@5 above 0.7 on your evaluation set.
