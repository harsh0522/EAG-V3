# Hallucination Detection

## Problem Statement

LLMs generate fluent, confident-sounding text even when the information is factually incorrect. Hallucinations in customer-facing or decision-support applications cause direct harm — wrong medical information, incorrect legal citations, fabricated product specifications. Detecting them at runtime is a critical safety requirement.

## Solution / Pattern

Hallucination detection combines three complementary approaches. Source grounding verification checks whether factual claims in the output are supported by the retrieved context; this is the most effective method for RAG systems where the ground truth is available. Self-consistency checking generates multiple outputs for the same input and flags claims that appear in fewer than 70% of outputs as potentially hallucinated. Uncertainty elicitation prompts the model to rate its own confidence in each factual claim and flags low-confidence claims for human review.

No single method is sufficient; deploy all three in a layered pipeline for high-stakes outputs.

## Key Details

- For RAG systems, implement atomic claim extraction: break the model's output into individual factual claims, then verify each claim against the retrieved chunks using a dedicated entailment model or a secondary LLM call. Claims without supporting chunk evidence should be marked as ungrounded.
- Self-consistency checking requires at least 3 independent samples (temperature 0.5–0.7) to produce meaningful agreement statistics; 5 samples give reliable estimates for most claims.
- NLI (Natural Language Inference) models specialized for hallucination detection (e.g., FactScore models) are faster and cheaper than using a frontier LLM for claim verification; use them for high-volume pipelines.
- Set the grounding threshold at 90% for safety-critical outputs: only claims supported by retrieved context with NLI confidence above 0.9 should be included in the final output without a disclaimer.
- Track the ungrounded claim rate as a production metric; rising rates indicate that queries are increasingly targeting topics not covered by the retrieval corpus and the corpus needs expansion.
- Present uncertainty signals to users when present: "The following information was not found in the retrieved sources and may require verification" — transparency about uncertainty builds appropriate user trust.
