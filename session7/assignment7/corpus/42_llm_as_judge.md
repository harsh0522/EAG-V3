# LLM-as-Judge

## Problem Statement

Human evaluation of generative AI outputs is expensive, slow, and difficult to scale. Automated metrics like BLEU and ROUGE are poor proxies for quality in open-ended generation tasks. LLM-as-judge — using a powerful model to evaluate the outputs of another model — offers a scalable middle ground.

## Solution / Pattern

LLM-as-judge uses a separate, capable model (often a frontier model) to evaluate outputs on a defined rubric. The judge prompt includes the original question, the model's output, and an explicit rubric with scoring dimensions and a scoring scale (typically 1–5 for each dimension). The judge outputs structured scores and a brief rationale for each score.

Validate the judge before relying on it: run it on 100 examples that have also been scored by at least 3 human annotators. The judge's correlation with human preference (measured by Spearman's rho) should be above 0.75 before it is trusted for automated evaluation.

## Key Details

- Use the same judge model consistently across evaluation runs; different models have different scoring biases, and mixing judges within a time series creates artificial performance signals.
- Position bias is a known failure mode: LLM judges favor responses in the first position when evaluating two candidates side-by-side. Mitigate by always running pairwise comparisons in both orders and averaging the results.
- Self-evaluation bias: a model evaluating its own outputs gives inflated scores; always use a different model as judge than the model being evaluated.
- The rubric must define what each score means with a concrete example; "5 = excellent" is too vague. "5 = the response fully answers the question with accurate information and no unnecessary content" is actionable.
- Aggregate judge scores over at least 50 examples per condition before drawing conclusions; single-example judge scores have high variance and are not representative.
- Include the judge's score in your structured logs and track judge score distribution over time; a systematic drift in scores (even without prompt changes) may indicate model behavior drift or evaluation distribution shift.
