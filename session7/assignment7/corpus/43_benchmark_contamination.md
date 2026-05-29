# Benchmark Contamination

## Problem Statement

Published evaluation benchmarks (MMLU, GSM8K, HumanEval) are frequently included in LLM training corpora, either deliberately or through web scraping of sites that discuss or display benchmark problems. Models that have seen benchmark problems during training achieve inflated scores that do not reflect genuine capability.

## Solution / Pattern

Defend against benchmark contamination by creating private evaluation sets that are never published, shared, or included in any training data pipeline. Private evaluations are the only reliable measure of model capability for benchmarks that have been publicly available for more than 6 months.

For benchmarks you use internally, compute n-gram overlap between your evaluation set and your training corpus; any evaluation example with more than 30% 8-gram overlap with training data should be considered potentially contaminated and flagged for removal.

## Key Details

- Contamination detection using 8-gram overlap is a standard approach; shorter n-gram sizes produce too many false positives, while longer ones miss paraphrased contamination.
- When evaluating an external model using published benchmarks, use the "dynamic" variant if available — versions that append a random suffix or slightly rephrase questions to prevent memorization-based performance.
- Performance on very recent benchmarks (released in the past 3 months) is more trustworthy than performance on old benchmarks; use benchmark release dates as a proxy for contamination risk.
- If benchmark performance exceeds human-level accuracy by a large margin (more than 15 percentage points), treat this as a contamination signal rather than evidence of superhuman capability, especially for benchmarks released before the model's training cutoff.
- Create a private holdout of 50 benchmark questions that are slight variations of known benchmark examples; a significant gap between public benchmark performance and private holdout performance (more than 10 percentage points) confirms contamination.
- Document contamination analysis results alongside all benchmark scores in evaluation reports; undisclosed contamination is a reproducibility and trust issue.
