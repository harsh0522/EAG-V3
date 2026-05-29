# Structured Output Prompting

## Problem Statement

Parsing natural language model outputs with regex or heuristics is brittle and creates maintenance burdens. When model output format drifts — a common occurrence across model versions — downstream parsing fails silently or produces corrupt data.

## Solution / Pattern

Structured output prompting constrains the model to emit valid JSON, XML, or another machine-readable format directly. Modern APIs offer JSON mode or function-calling/tool-use interfaces that enforce schema compliance at the sampling layer, making format violations impossible by construction. When using these interfaces, define your schema with strict types and mark every field as required unless the field's absence carries semantic meaning.

For models or endpoints without native schema enforcement, include the target schema in the prompt and follow it with the instruction "Respond only with valid JSON matching the above schema. Do not include markdown formatting, code fences, or any text before or after the JSON object."

## Key Details

- Always validate model output against your schema using a library (Pydantic, Zod, etc.) before passing it to downstream systems; even JSON-mode APIs can produce valid JSON that does not match your schema.
- When a model output fails schema validation, retry with an augmented prompt that includes the invalid output and the validation error message; models successfully self-correct on the first retry approximately 78% of the time.
- Design schemas with the minimum number of fields necessary; each additional optional field increases the probability of hallucinated values by approximately 4–7%.
- Nested objects more than 3 levels deep significantly degrade schema compliance; flatten your schema and reconstruct nesting in application code when possible.
- For arrays, specify min and max length in the schema or instruction; unbounded arrays frequently result in the model truncating mid-array or padding with empty objects.
- Log all schema validation failures and review them weekly; a rising failure rate is a leading indicator of model behavior drift before it manifests in downstream metrics.
