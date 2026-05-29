# RLHF vs. DPO: Choosing the Right Alignment Method

## Problem Statement

Teams seeking to align model behavior with human preferences face a choice between Reinforcement Learning from Human Feedback (RLHF) and Direct Preference Optimization (DPO). Both use preference data but differ substantially in complexity, computational cost, and stability.

## Solution / Pattern

RLHF trains a separate reward model on preference data, then uses reinforcement learning (typically PPO) to optimize the language model to maximize the reward model's score. DPO eliminates the separate reward model and directly optimizes the language model on preference pairs using a closed-form objective derived from the optimal RLHF policy. DPO is simpler to implement, more stable to train, and requires approximately 3x less compute than RLHF.

Choose RLHF when you need fine-grained control over the reward function (adding safety constraints, multi-objective balancing) and have the engineering capacity to maintain a separate reward model pipeline. Choose DPO when your alignment goal is well-captured by preference pairs and you want a simpler, more reproducible training process.

## Key Details

- DPO requires high-quality preference pairs; noisy labels degrade DPO more severely than RLHF because DPO has no reward model to average out label noise. Label agreement rate in preference pairs should be above 80% before using DPO.
- Minimum preference dataset size for DPO: 2,000 pairs for style alignment; 5,000–10,000 pairs for safety-relevant behavior changes.
- RLHF with PPO is inherently unstable; use a KL-divergence penalty with beta=0.1 to 0.3 to prevent reward hacking (the model exploiting reward model blind spots rather than genuinely improving).
- DPO beta parameter controls the deviation from the reference model; lower beta (0.1) allows larger behavioral changes, higher beta (0.5) stays closer to the reference. Start at beta=0.1 and increase if the model diverges from desired behavior on held-out examples.
- Both methods require a reference model (the base SFT checkpoint) that is kept frozen during alignment training; the reference model is critical for computing the KL constraint.
- Evaluate alignment success not just on the preference test set but also on adversarial examples specifically designed to elicit the behaviors you trained against.
