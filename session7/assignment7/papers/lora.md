# LoRA: Low-Rank Adaptation of Large Language Models
**Authors:** Edward J. Hu, Yelong Shen, Phillip Wallis, Zeyuan Allen-Zhu, Yuanzhi Li, Shean Wang, Lu Wang, Weizhu Chen  
**Year:** 2022  
**Venue:** ICLR

## Abstract

An important paradigm of natural language processing consists of large-scale pre-training on general domain data and adaptation to particular tasks or domains. As we pre-train larger models, full fine-tuning, which retrains all model parameters, becomes less feasible. Using GPT-3 175B as an example — deploying independent instances of fine-tuned models, each with 175B parameters, is prohibitively expensive. We propose Low-Rank Adaptation, or LoRA, which freezes the pre-trained model weights and injects trainable rank decomposition matrices into each layer of the Transformer architecture, greatly reducing the number of trainable parameters for downstream tasks.

## Key Contributions

### 1. Low-Rank Weight Decomposition

LoRA is based on the hypothesis that the change in weights during model adaptation has a low intrinsic rank. For a pre-trained weight matrix W₀ ∈ ℝ^(d×k), LoRA constrains the update ΔW by representing it as a low-rank decomposition:

W₀ + ΔW = W₀ + BA

Where:
- B ∈ ℝ^(d×r)
- A ∈ ℝ^(r×k)
- r << min(d, k) is the rank

During training, W₀ is frozen and only A and B are optimized. At initialization, A is random Gaussian and B is zero, so ΔW = BA = 0 at the start of training. The output is scaled by α/r where α is a constant.

This decomposition means the number of trainable parameters is 2 × d × r instead of d × k, achieving up to 10,000× reduction in trainable parameters.

### 2. No Inference Overhead

A key advantage of LoRA over other parameter-efficient methods is zero inference latency overhead. After training, the LoRA matrices can be merged with the original weights:

W = W₀ + BA

The resulting matrix W has exactly the same shape as W₀, so the model can be deployed identically to a fully fine-tuned model with no additional computation at inference time. Adapters (an alternative approach) add sequential modules that increase inference latency; LoRA avoids this.

### 3. Efficient Multi-Task Deployment

Because LoRA adapters are small (a few MB vs. tens of GB for the full model), it becomes practical to maintain a single base model and swap adapter weights for different tasks. This enables:

- Task switching with minimal memory: swap the LoRA matrices (small) rather than the full model
- Efficient serving: store one copy of the 175B base model and many small per-task adapters
- Composition: combine adapters trained for different aspects of behavior

## Application to Transformers

LoRA is applied to the attention weight matrices of Transformer models. Specifically, the paper applies LoRA to the query (W_q), value (W_v), key (W_k), and output projection (W_o) matrices within each attention layer.

Empirically, adapting only W_q and W_v (the query and value matrices) provides most of the benefit. The feed-forward layers contribute less to task-specific adaptation and are typically left frozen.

For GPT-3 175B:
- Full fine-tuning: 175B trainable parameters
- LoRA (r=4, applied to W_q and W_v): 4.7M trainable parameters — a 37,000× reduction
- VRAM during training: reduced by 2/3 compared to full fine-tuning
- Checkpoint size: 350MB vs 350GB

## Experimental Results

### Natural Language Understanding (GLUE Benchmark)
- LoRA with RoBERTa-large: competitive with full fine-tuning across all tasks
- Outperforms adapter tuning and prefix tuning while using fewer parameters

### Natural Language Generation (GPT-2 Medium and Large)
- LoRA matches full fine-tuning performance on E2E NLG and WebNLG benchmarks
- Outperforms adapter layers and prefix tuning

### Large-Scale Language Models (GPT-3 175B)
- LoRA trained on WikiSQL: 73.4% accuracy vs full fine-tuning: 73.8%
- LoRA trained on MNLI-matched: 91.7% vs full fine-tuning: 89.5% (LoRA outperforms!)
- Training cost reduced from $3.5M to approximately $35K for a 175B model

## Rank Sensitivity Analysis

The paper studies how rank r affects performance:
- Rank r=1 already achieves strong results on many tasks
- Performance generally plateaus around r=4 to r=16 depending on task complexity
- Higher ranks provide marginal improvements for most tasks
- The weight update ΔW for specific tasks can often be captured in very low-dimensional subspaces

This supports the core hypothesis that task-specific adaptations live in low-dimensional manifolds within the full weight space.

## Comparison with Other Parameter-Efficient Methods

| Method | Inference Overhead | VRAM Reduction | Trainable Params | Task Switching |
|--------|-------------------|----------------|-----------------|----------------|
| Full fine-tuning | None | None | 100% | No (full model per task) |
| Adapter layers | Yes (~30% slower) | Moderate | ~0.5-3% | Hard (sequential modules) |
| Prefix tuning | None | Moderate | ~0.1-0.5% | Easy (prefix swap) |
| LoRA | None | Large | ~0.01-0.1% | Easy (small adapter) |

## Impact and Widespread Adoption

LoRA has become the standard approach for fine-tuning large language models in practice. Nearly every open-source fine-tuned model release (Alpaca, Vicuna, LLaMA fine-tunes) uses LoRA or QLoRA (quantized LoRA). The HuggingFace PEFT library provides a canonical implementation. Extensions include:

- **QLoRA**: combine 4-bit quantization with LoRA to fine-tune 65B models on a single GPU
- **DoRA**: weight decomposition into magnitude and direction components
- **LoftQ**: better initialization for quantized LoRA models
- **AdaLoRA**: adaptive rank allocation based on importance scores
