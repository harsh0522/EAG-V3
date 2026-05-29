# Direct Preference Optimization: Your Language Model is Secretly a Reward Model
**Authors:** Rafael Rafailov, Archit Sharma, Eric Mitchell, Stefano Ermon, Christopher D. Manning, Chelsea Finn  
**Year:** 2023  
**Venue:** NeurIPS

## Abstract

While large-scale unsupervised language models (LMs) learn broad world knowledge and some notion of reasoning ability, achieving precise control of their behavior is difficult due to the completely unsupervised nature of their training. Existing methods for gaining such steerability collect human labels of the relative quality of model generations and fine-tune the unsupervised LM to align with these preferences, often with reinforcement learning from human feedback (RLHF). However, RLHF is a complex and often unstable procedure, first fitting a reward model that reflects the human preferences, and then fine-tuning the large unsupervised LM using reinforcement learning to maximize this estimated reward. In this paper, we introduce a new parameterization of the reward model in RLHF that enables extraction of the corresponding optimal policy in closed form, allowing us to solve the standard RLHF problem with only a simple classification loss.

## Key Contributions

### 1. The DPO Objective

Direct Preference Optimization (DPO) derives a direct mapping between the preference data and the optimal language model policy. The key insight is that the optimal policy for the standard RLHF objective can be expressed analytically in terms of the reference model and the reward function.

Given preference pairs (y_w, y_l) for the same prompt x (where y_w is preferred over y_l), the DPO loss is:

L_DPO(π_θ; π_ref) = -E[(x,y_w,y_l) ~ D] [log σ(β log (π_θ(y_w|x) / π_ref(y_w|x)) - β log (π_θ(y_l|x) / π_ref(y_l|x)))]

Where:
- π_θ is the policy being trained
- π_ref is the frozen reference policy
- β controls the deviation from the reference policy
- σ is the sigmoid function

This elegant formulation eliminates the need for an explicit reward model.

### 2. Eliminating the Reward Model

Traditional RLHF requires training a separate reward model from human comparison data and then using reinforcement learning (typically PPO) to optimize the language model against this reward model. This two-stage process is computationally expensive and introduces multiple sources of instability:

- The reward model may overfit to the training preference data
- RL training with PPO requires careful hyperparameter tuning
- The reward model may be exploited (reward hacking) by the RL policy

DPO collapses these two stages into a single supervised learning objective. The reference model π_ref (the initial fine-tuned model) serves implicitly as the "reward model" through the ratio parameterization.

### 3. Implicit Reward Parameterization

The paper shows that any reward function r(x, y) can be reparameterized as:

r(x, y) = β log (π(y|x) / π_ref(y|x)) + β log Z(x)

Where Z(x) is the partition function. When used in the Bradley-Terry preference model, the partition function cancels, yielding the DPO loss. This means optimizing DPO implicitly defines and optimizes a reward function without ever explicitly computing it.

## Experimental Results

### Sentiment Control
- DPO achieves similar reward with higher diversity compared to PPO (KL-constrained RL)
- DPO is more computationally efficient (no reward model training or RL loop)

### Summarization (TL;DR)
- DPO-trained model preferred over SFT baseline: 61% of the time
- PPO-trained model preferred over SFT baseline: 55% of the time
- DPO outperforms PPO while being simpler and more stable

### Single-Turn Dialogue (Anthropic HH Dataset)
- DPO achieves competitive win rates against PPO
- DPO uses significantly less GPU memory during training (no reward model)

## Comparison with RLHF/PPO

| Aspect | RLHF + PPO | DPO |
|--------|------------|-----|
| Reward model | Required (trained separately) | Implicit (not trained) |
| RL optimization | Required (PPO) | Not required |
| Training stages | 3 (SFT → RM → RL) | 2 (SFT → DPO) |
| Hyperparameters | Many (RL-specific) | Fewer (β only) |
| Stability | Lower | Higher |
| Computational cost | Higher | Lower |
| Memory requirements | Higher | Lower |

## Limitations and Discussion

1. DPO assumes access to pairwise preference data, which may be expensive to collect
2. The method relies on the reference model being a good starting point
3. Like RLHF, DPO may overfit to the preference annotation distribution
4. The choice of β significantly affects the trade-off between alignment and capability preservation

## Impact

DPO has become one of the most widely used alignment methods in practice. Its simplicity, stability, and competitive performance have made it the preferred approach for aligning open-source language models. Many popular models including Zephyr, Mistral-7B-Instruct, and others have used DPO or variants (such as IPO, KTO, ORPO) derived from its core insight.

The paper demonstrates that explicit reinforcement learning may not be necessary for alignment: the preference optimization objective can be expressed as a simple supervised classification problem over paired examples.
