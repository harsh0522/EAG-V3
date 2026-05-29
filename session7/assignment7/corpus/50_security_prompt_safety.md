# Security and Prompt Safety

## Problem Statement

LLM applications face unique security threats beyond traditional software vulnerabilities: prompt injection, jailbreaking, data exfiltration through model outputs, and adversarial inputs designed to extract training data or system configuration. These threats require security controls at the AI layer in addition to standard application security practices.

## Solution / Pattern

Implement a defense-in-depth security strategy for LLM applications. At the input layer, classify all incoming requests for adversarial patterns before passing them to the model. At the model layer, use fine-tuned refusal capabilities and enforce behavioral constraints through system prompt design. At the output layer, scan model outputs for sensitive content (PII, system configuration, training data fragments) before delivering them to users.

Never rely on a single security control; assume each layer can be bypassed individually and design so that bypassing any single layer does not compromise the overall system.

## Key Details

- Use a lightweight classifier trained on adversarial examples to screen inputs before model inference; a good classifier should reject more than 95% of known attack patterns with fewer than 1% false positives on benign traffic.
- Define a list of "canary" phrases embedded in your system prompt (unique strings not found in training data); if these phrases appear in model outputs, it indicates the model has been coerced into revealing system configuration — alert immediately.
- Implement output scanning for PII using a regex + entity recognition pipeline before delivering responses; do not rely on the model to redact PII from its own outputs, as models hallucinate redaction inconsistently.
- Rate-limit requests by user identity at 100 requests per hour as a default; accounts exceeding this limit at unusual hours are strong signals of automated adversarial probing.
- Log all requests that trigger safety refusals in a separate security event log; analyze this log weekly to identify new attack patterns and update the input classifier.
- Conduct red-team exercises targeting both prompt injection and jailbreak vulnerabilities quarterly; document all successful attacks and track remediation time as a security KPI.
