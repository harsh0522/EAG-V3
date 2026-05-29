# Catastrophic Forgetting Prevention

## Problem Statement

Fine-tuning a model on domain-specific data often degrades its performance on capabilities present in the base model. A model fine-tuned for legal document analysis may lose its ability to write Python code or perform arithmetic. This phenomenon, called catastrophic forgetting, is a persistent challenge in continual learning systems.

## Solution / Pattern

Prevent catastrophic forgetting by mixing replay data from the pre-training distribution into the fine-tuning dataset. A standard replay ratio is 10–20% general data (sampled from the pre-training corpus or a high-quality subset like open-source code and diverse web text) mixed with 80–90% domain-specific data. The replay data anchors the model to its general capabilities while the domain data shifts its specialization.

For parameter-efficient methods like LoRA, catastrophic forgetting is significantly reduced because only a small fraction of parameters are modified. The base model weights remain frozen and retain general capabilities, while the adapter weights encode the domain specialization.

## Key Details

- Measure forgetting explicitly: evaluate the model on a general capability benchmark (MMLU, HumanEval for code, GSM8K for math) before and after fine-tuning; a drop of more than 5 percentage points on any benchmark indicates significant forgetting.
- Use Elastic Weight Consolidation (EWC) for full fine-tuning when replay data is not available; EWC adds a regularization term that penalizes changes to weights that were important for pre-training tasks. The EWC lambda hyperparameter should be tuned on a validation set covering both old and new tasks.
- Learning rate is the primary driver of forgetting in full fine-tuning; a learning rate above 5e-5 dramatically increases forgetting risk. Use 1e-5 to 2e-5 for fine-tuning when preserving general capabilities matters.
- Monitor the loss on replay data during fine-tuning; if replay loss increases faster than domain data loss decreases, reduce the learning rate or increase the replay ratio.
- Test for forgetting on a schedule: run the full capability evaluation suite after every 1,000 training steps, not just at the end of training; catching forgetting early allows adjusting hyperparameters before significant capability is lost.
