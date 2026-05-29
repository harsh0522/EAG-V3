# Output Validation

## Problem Statement

Model outputs that pass through to downstream systems without validation can propagate errors silently. A malformed JSON response can crash a parsing pipeline; an output that violates a business rule (a recommended dosage outside a safe range, a financial figure with incorrect units) can cause downstream harm.

## Solution / Pattern

Output validation should be implemented as a multi-stage gate between model output and downstream consumption. Stage 1 validates format: does the output conform to the expected schema? Stage 2 validates constraints: do all values fall within permitted ranges and types? Stage 3 validates business rules: does the output satisfy domain-specific requirements (e.g., all cited sources must exist in the retrieval corpus)? Outputs failing any stage are either corrected (via a self-correction retry) or rejected with a structured error.

Implement validation using schema libraries for stages 1 and 2, and a secondary LLM call or rule engine for stage 3 business rule validation.

## Key Details

- On format validation failure, retry with an augmented prompt that includes the invalid output and the specific validation error; models self-correct format errors on the first retry approximately 78% of the time.
- Set a maximum of 2 retries for self-correction; beyond 2, the model is unlikely to self-correct and additional retries waste tokens. After 2 failures, return a structured error to the calling system.
- Constraint validation (Stage 2) should be implemented in application code, not as a model call; validating that a number is within range or a date is valid is a deterministic operation that does not require a model.
- Log all validation failures with the input, the invalid output, and the failure reason; this log is the primary data source for identifying systematic prompt engineering issues.
- For numerical outputs, validate not just range but precision; a financial figure expressed as "approximately $1.2 million" fails precision validation if the downstream system requires an exact integer.
- Apply output validation to streaming outputs as well as complete responses; validate the final assembled output from a stream before releasing it to downstream systems.
