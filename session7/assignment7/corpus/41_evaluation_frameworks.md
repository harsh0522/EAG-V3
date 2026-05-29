# Evaluation Frameworks

## Problem Statement

Without a systematic evaluation framework, AI system improvements are measured by intuition or anecdote. This leads to regressions being shipped undetected, A/B tests being inconclusive due to insufficient power, and teams spending engineering time on changes that don't actually improve user-facing quality.

## Solution / Pattern

Build an evaluation framework before deploying to production, not after. The framework should include: a curated evaluation set of 200–500 examples with gold-standard answers or human preference ratings, automated metrics appropriate to the task (BLEU for translation, F1 for extraction, accuracy for classification), and an LLM-as-judge scoring function for tasks where no automated metric is sufficient.

Run the full evaluation suite on every significant change (prompt edit, model update, retrieval configuration change) before deployment. Track all evaluation runs in a versioned experiment log with the git commit, model version, and full metric results.

## Key Details

- Evaluation sets must be refreshed quarterly; evaluation data that mirrors training data or that models have been implicitly optimized against produces over-optimistic estimates of real-world quality.
- For generative tasks, use at least 3 automated metrics rather than one; single metrics are gameable and may not capture all dimensions of quality relevant to users.
- Statistical significance is required for claiming improvements: with a 200-example evaluation set, a 3 percentage point difference in accuracy represents a statistically significant improvement at p=0.05; differences smaller than this are within noise.
- Stratify your evaluation set by task difficulty (easy/medium/hard) and by query type; an aggregate accuracy improvement that comes entirely from easier examples and degrades on hard examples is often not a real improvement.
- Track metric distributions over time in a dashboard; a metric that improves on average but with increasing variance indicates a regression in reliability even if the mean improves.
- Human evaluation is the gold standard but should be reserved for major releases; for routine changes, LLM-as-judge with a validated judge model is an acceptable proxy if calibrated against human labels.
