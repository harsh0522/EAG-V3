# Embedding Model Selection

## Problem Statement

Embedding model performance varies enormously by domain, language, and task type. A model that ranks first on the MTEB benchmark may underperform a smaller, domain-specific model on your actual retrieval task because benchmark corpora rarely match production data distributions.

## Solution / Pattern

Select embedding models by benchmarking on a representative sample of your actual retrieval task, not on public benchmarks alone. Collect 200–500 query-document pairs with human relevance labels from your domain. Run candidate models on this set and measure Recall@5 and MRR@10. The model with the best domain-specific performance wins, even if it is smaller or newer.

Consider three selection axes: embedding dimension (higher = more expressive but slower and more memory-intensive), max sequence length (longer = can embed full documents without truncation), and inference cost (API vs. self-hosted). The optimal choice balances all three against your latency, cost, and accuracy requirements.

## Key Details

- Embedding dimension of 768–1024 covers most production use cases; 1536-dimension models offer marginal improvements at 2x the storage and compute cost — only justified for tasks with very fine-grained semantic distinctions.
- Truncation is the most common silent failure in embedding pipelines; always check whether your chunks exceed the model's max sequence length and either split or summarize chunks that do.
- Self-hosted embedding inference on a single A10G GPU can process approximately 50,000 text chunks per hour at batch size 64; benchmark your hardware before deciding between API and self-hosted.
- Models trained with Matryoshka Representation Learning (MRL) allow you to truncate embedding dimensions post-hoc without re-embedding; this flexibility is valuable when storage costs become a constraint.
- Re-embed the entire corpus when switching embedding models; embeddings from different models are not comparable and mixing them in a single index produces retrieval failures.
- Monitor embedding latency as a p99 metric in production; API embedding latency spikes are a common cause of retrieval timeouts that are misattributed to the generation model.
