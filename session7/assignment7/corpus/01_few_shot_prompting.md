# Few-Shot Prompting

## Problem Statement

Large language models often struggle to match the exact output format, tone, or reasoning style a production application requires. Zero-shot instructions can be ambiguous, leading to inconsistent outputs across calls and brittle downstream parsing.

## Solution / Pattern

Few-shot prompting provides the model with 2–8 worked examples of input-output pairs before the actual query. These examples act as a strong implicit specification of format, reasoning depth, and content constraints. The model infers patterns from the examples rather than relying solely on explicit instructions.

Construct examples by sampling from real production data that covers edge cases. Include at least one negative example if the task involves rejection or refusal. Order examples from simplest to most complex to scaffold the model's reasoning toward the final, more complex query.

## Key Details

- Use 3–5 examples for classification and extraction tasks; 6–8 examples for multi-step reasoning chains.
- Place examples after the system prompt but before the user message to preserve the role hierarchy.
- Rotate example sets across sessions to prevent the model from pattern-matching on example identifiers rather than reasoning through the problem.
- Embedding-based example selection outperforms random selection: retrieve the 4 nearest neighbors to the query from your example pool using cosine similarity against a fast index, then pass those 4 to the prompt.
- Budget 30–40% of your context window for examples; if examples exceed this, switch to a compressed format that removes verbose reasoning traces and retains only input-output pairs.
- Evaluate few-shot prompts on at least 200 held-out examples before deploying; accuracy improvements below 3 percentage points over zero-shot typically do not justify the added token cost in high-volume pipelines.
