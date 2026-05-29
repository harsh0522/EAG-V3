# Instruction Tuning

## Problem Statement

Base language models predict the next token in a document — they are not inherently designed to follow instructions or engage in multi-turn dialogue. Without instruction tuning, a base model will continue a user prompt as a document continuation rather than respond as an assistant.

## Solution / Pattern

Instruction tuning (also called supervised fine-tuning for alignment) trains the base model on a dataset of instruction-response pairs formatted as conversations. The model learns to recognize the instruction format and generate appropriate responses rather than continuations. The quality and diversity of instruction data matters more than its quantity — 10,000 high-quality, diverse instruction pairs outperform 100,000 low-quality, repetitive ones.

Format instruction data using the target model's chat template (e.g., `<|user|>...<|assistant|>...`), and train with a loss mask that only computes loss on the assistant response tokens — not the instruction tokens. This ensures the model is trained to generate responses, not to predict the instruction.

## Key Details

- Instruction diversity is the primary driver of generalization; cover at least 50 distinct task categories in the training dataset to prevent the model from specializing on a narrow task distribution.
- Use at least 15% "refusal" examples — cases where the correct response is to decline the request; models trained without refusal examples do not generalize the ability to refuse.
- Learning rate for instruction tuning: 1e-5 to 5e-5 with a cosine decay schedule; higher learning rates cause catastrophic forgetting of pre-training capabilities.
- Evaluate instruction-tuned models on both the target task and a general instruction-following benchmark (e.g., MT-Bench, AlpacaEval) to verify that specialization has not degraded general capability.
- Apply instruction tuning before any alignment fine-tuning (RLHF, DPO); alignment fine-tuning on a base model without instruction tuning produces unstable and unpredictable results.
- Monitor training loss curves for instruction-only tokens and response tokens separately; a model where instruction loss rises while response loss falls is leaking the instruction distribution into the response.
