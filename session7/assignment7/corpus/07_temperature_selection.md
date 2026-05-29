# Temperature Selection

## Problem Statement

Temperature is the most frequently misunderstood sampling parameter. Engineers often default to 0.7 or 1.0 across all tasks, leading to unpredictable output variation in structured tasks and unnecessary rigidity in creative tasks.

## Solution / Pattern

Temperature controls the sharpness of the probability distribution over next tokens. At temperature 0.0, the model always selects the highest-probability token (greedy decoding). At higher temperatures, low-probability tokens get a larger share of the sampling probability, increasing output diversity but also error rates.

Match temperature to task type: deterministic tasks (code generation, structured extraction, classification) should use 0.0–0.1; balanced tasks (question answering, summarization) should use 0.2–0.4; creative tasks (brainstorming, story generation) should use 0.6–0.9. Values above 1.0 produce incoherent output for most production tasks and should be avoided.

## Key Details

- Temperature 0.0 does not guarantee identical outputs across identical inputs because of floating-point non-determinism in GPU execution; for true reproducibility, combine low temperature with a fixed seed parameter if the API supports it.
- For classification tasks, measure accuracy at temperature 0.0, 0.1, and 0.2; in most cases, 0.0 and 0.1 perform within 1% of each other, and 0.2 introduces measurable degradation for tasks with more than 5 classes.
- Top-p (nucleus sampling) at 0.9 combined with temperature 0.7 is a robust default for creative generation; this combination prevents the long tail of incoherent tokens while maintaining diversity.
- When using temperature for structured output tasks, prefer temperature 0.0 over relying solely on JSON mode to enforce format compliance; the two mechanisms are complementary, not redundant.
- Avoid tuning temperature as the primary lever for changing output length; temperature affects token selection probabilities, not sequence length — use max_tokens for length control.
