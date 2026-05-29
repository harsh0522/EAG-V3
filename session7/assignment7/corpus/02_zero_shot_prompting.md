# Zero-Shot Prompting

## Problem Statement

Collecting labeled examples for few-shot prompting is expensive and time-consuming. For novel tasks or rapidly changing domains, maintaining an up-to-date example bank creates operational overhead that slows iteration cycles.

## Solution / Pattern

Zero-shot prompting relies entirely on clear, structured instructions without worked examples. The key is to front-load the instruction with a role declaration, the task objective, explicit output format specification, and any constraint list before presenting the content to process. Models trained with instruction tuning respond reliably to well-structured zero-shot prompts for a wide range of tasks.

Break complex tasks into explicit numbered steps within the instruction. Instead of asking the model to "summarize and extract entities," instruct it to "(1) write a 2-sentence summary, (2) list all named organizations, (3) list all dates mentioned." Decomposing the task reduces errors caused by the model silently prioritizing one sub-task over another.

## Key Details

- Keep the core instruction under 150 tokens; longer instructions increase the probability of the model attending to only the first or last sentence of the instruction block.
- Use imperative verbs at the start of each instruction clause: "Extract," "Return," "Ignore," "Format as JSON."
- For structured output, include a schema example inline (e.g., `{"field": "value"}`) even without a filled example — schema alone improves format compliance by approximately 40% over plain text descriptions.
- If zero-shot accuracy on your evaluation set falls below 85%, add at least 2 examples rather than rewriting the instruction; instruction rewrites tend to improve performance by 2–5% whereas even 2 examples improve it by 8–15%.
- Temperature should be set to 0.0 for zero-shot tasks requiring deterministic structure; raise to 0.2–0.4 only for open-ended generation tasks.
