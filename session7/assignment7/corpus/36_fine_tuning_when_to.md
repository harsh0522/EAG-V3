# Fine-Tuning: When to Use It

## Problem Statement

Fine-tuning is often applied prematurely, before prompt engineering has been exhausted, or inappropriately, for tasks where the model's base capabilities are sufficient. Fine-tuning is expensive, creates model versioning overhead, and requires continuous maintenance — it should be a deliberate decision, not a default.

## Solution / Pattern

Fine-tuning is justified in exactly three situations: (1) the target behavior is so domain-specific that no amount of prompting produces consistent correct outputs; (2) the latency or cost requirements cannot be met with a large model and a small fine-tuned model could do the job; (3) the output format is so specialized (a proprietary structured format, a domain-specific language) that prompting alone cannot reliably achieve it.

Before committing to fine-tuning, run a two-week intensive prompt engineering sprint. If prompt engineering on the best available model cannot reach the accuracy target, fine-tuning a smaller model is worth exploring.

## Key Details

- Minimum dataset size for reliable fine-tuning: 500 high-quality examples for format adaptation tasks, 1,000–5,000 examples for domain knowledge tasks, 10,000+ examples for behavior alignment tasks. Below these thresholds, overfitting to the training set is the dominant failure mode.
- Reserve 15% of the dataset as a test set held out from both training and validation; fine-tuning experiments frequently use the full dataset for training and overstate performance.
- Measure fine-tuned model performance against the base model + best prompt on your actual evaluation set; the fine-tuned model should outperform by at least 10 percentage points to justify the ongoing maintenance cost.
- Fine-tuned models require re-training whenever the underlying task distribution shifts; budget at least one re-training cycle per quarter for production models.
- Use LoRA fine-tuning for 7B–70B parameter models; full fine-tuning at this scale requires significant GPU infrastructure and LoRA achieves comparable performance at approximately 10% of the training cost.
- Track training loss and validation loss separately across epochs; a widening gap between the two (training loss still falling while validation loss rises) is the key signal to stop training.
