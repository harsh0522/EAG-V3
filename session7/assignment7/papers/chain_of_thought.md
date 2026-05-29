# Chain-of-Thought Prompting Elicits Reasoning in Large Language Models
**Authors:** Jason Wei, Xuezhi Wang, Dale Schuurmans, Maarten Bosma, Brian Ichter, Fei Xia, Ed Chi, Quoc Le, Denny Zhou  
**Year:** 2022  
**Venue:** NeurIPS

## Abstract

We explore how generating a chain of thought — a series of intermediate reasoning steps — significantly improves the ability of large language models to perform complex reasoning. In particular, we show how such reasoning abilities emerge naturally in sufficiently large language models via a simple method called chain-of-thought prompting, where a few chain-of-thought demonstrations are provided as examples in prompting.

## Key Contributions

### 1. Chain-of-Thought Prompting Method

The paper introduces chain-of-thought prompting as a method for eliciting multi-step reasoning from language models. Rather than providing the model with only a question and the final answer, the demonstrations include a sequence of natural language intermediate steps that lead to the final answer.

For example, instead of:
- Input: "Roger has 5 tennis balls. He buys 2 more cans of tennis balls. Each can has 3 tennis balls. How many tennis balls does he have now?"
- Answer: "11"

Chain-of-thought prompting provides:
- Input: same question
- Chain of thought: "Roger started with 5 balls. 2 cans of 3 tennis balls each is 6 tennis balls. 5 + 6 = 11."
- Answer: "11"

This intermediate reasoning process allows the model to decompose multi-step problems into individual steps, making errors more traceable and interpretable.

### 2. Emergent Reasoning in Large Models

A key finding is that chain-of-thought prompting is an emergent ability that only manifests in models with approximately 100 billion parameters or more. Smaller models showed little benefit from chain-of-thought demonstrations, and in some cases performance degraded relative to standard prompting.

This suggests that the ability to perform coherent multi-step reasoning is an emergent property of scale. The model must already have sufficient capacity to understand and follow complex reasoning chains before chain-of-thought prompting can be effective.

### 3. Broad Applicability Across Task Types

Chain-of-thought prompting improves performance across a wide variety of reasoning tasks:

- **Arithmetic reasoning:** GSM8K (grade school math), SVAMP, ASDiv, MultiArith
- **Commonsense reasoning:** CommonsenseQA, StrategyQA
- **Symbolic reasoning:** Last letter concatenation, Coin flip problems

The method works particularly well on tasks that benefit from being decomposed into multiple steps. For tasks that do not require multi-step reasoning, the benefit is marginal.

## Experimental Results

- PaLM 540B with chain-of-thought prompting achieves 56.9% on GSM8K, outperforming fine-tuned GPT-3 (33%) and approaching human performance
- On StrategyQA commonsense benchmark: 65.4% accuracy with chain-of-thought vs 60.8% without
- LaMDA 137B with chain-of-thought achieves 36.5% on GSM8K vs 17.9% without

## Technical Details

The method uses few-shot prompting with 8 examples per task, each annotated with a chain of thought. No fine-tuning is required. The chains of thought are written by human annotators to provide natural reasoning traces. Temperature is set to 0.0 (greedy decoding) or low temperatures for reproducible results.

## Limitations and Discussion

The authors note several limitations:

1. The intermediate reasoning steps are not guaranteed to be correct even when the final answer is right — the model may arrive at correct answers through incorrect reasoning paths.
2. The method only benefits very large models (100B+ parameters), making it inaccessible for resource-constrained applications.
3. Generating chain-of-thought reasoning increases inference cost proportionally to the length of the reasoning chain.
4. The quality of the chain-of-thought demonstrations affects performance, requiring careful human annotation.

## Influence on Subsequent Work

This paper sparked extensive follow-up research including: zero-shot chain-of-thought ("Let's think step by step"), self-consistency prompting (sampling multiple reasoning paths and selecting by majority vote), tree-of-thought (exploring branching reasoning trees), and program-of-thought (expressing reasoning as executable code). The core insight — that intermediate steps improve model reasoning — has become foundational to modern prompt engineering.
