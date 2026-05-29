# LoRA: A Practical Guide

## Problem Statement

Low-Rank Adaptation (LoRA) is the dominant technique for parameter-efficient fine-tuning but its hyperparameters — rank, alpha, learning rate, target modules — are poorly understood by most practitioners, leading to underperforming adapters or unnecessary compute expenditure.

## Solution / Pattern

LoRA injects trainable low-rank matrices into specific weight matrices of the base model. Only these adapter matrices are trained; the base model weights remain frozen. The rank parameter (r) controls the expressiveness of the adapter: low rank (r=4, r=8) suits format and style adaptation; higher rank (r=16, r=32) suits domain knowledge injection. The alpha parameter controls the scaling of the adapter's contribution; setting alpha to twice the rank value (alpha = 2r) is a robust default.

Target the attention query and value projection matrices (q_proj, v_proj) at minimum; adding the key projection and feedforward intermediate layers incrementally until performance plateaus provides a systematic search strategy for target module selection.

## Key Details

- Training hyperparameters: learning rate 1e-4 to 3e-4 for LoRA adapters (lower than full fine-tuning because only adapter weights are being trained); batch size 16 or 32 with gradient accumulation to simulate larger batches; 3–5 epochs for most tasks, stopping early when validation loss plateaus.
- Rank r=16 with alpha=32 targeting q_proj and v_proj covers approximately 85% of fine-tuning tasks at a training cost 10–15x lower than full fine-tuning.
- LoRA adapter files for a 7B parameter model are typically 50–300MB depending on rank and target modules; they load on top of a base model in seconds, enabling fast A/B testing of adapter variants.
- Merge the LoRA adapter into the base model weights for production serving; running inference with a separate adapter adds approximately 15% latency overhead versus the merged model.
- Evaluate LoRA adapters on both the fine-tuning task and a suite of general capability benchmarks; LoRA fine-tuning can induce catastrophic forgetting in adjacent capabilities not present in the training set.
- Use 4-bit quantization (QLoRA) for fine-tuning models too large to fit in full precision on available GPUs; QLoRA achieves comparable results to full-precision LoRA for most tasks.
