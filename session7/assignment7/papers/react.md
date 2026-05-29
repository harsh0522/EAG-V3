# ReAct: Synergizing Reasoning and Acting in Language Models
**Authors:** Shunyu Yao, Jeffrey Zhao, Dian Yu, Nan Du, Izhak Shafran, Karthik Narasimhan, Yuan Cao  
**Year:** 2023  
**Venue:** ICLR

## Abstract

While large language models (LLMs) have demonstrated impressive capabilities across tasks in language understanding and interactive decision making, their abilities for reasoning (e.g. chain-of-thought prompting) and acting (e.g. action plan generation) have largely been studied as separate topics. In this paper, we explore the use of LLMs to generate both reasoning traces and task-specific actions in an interleaved fashion, allowing for greater synergy between the two: reasoning traces help the model induce, track, and update action plans as well as handle exceptions, while actions allow it to interface with external sources such as knowledge bases or environments to gather additional information.

## Key Contributions

### 1. The ReAct Paradigm

ReAct introduces a new paradigm that combines reasoning traces with action calls in a single LLM generation. The model generates thought-action-observation triplets in sequence:

- **Thought:** The model reasons about its current situation and decides what to do
- **Action:** The model takes an action (e.g., search, lookup, finish)
- **Observation:** The result of the action is inserted into the context

This interleaving allows the model to update its reasoning based on new information gathered from external tools, and to use reasoning to decide which tools to call and with what arguments.

### 2. Grounded Reasoning via External Knowledge

A key limitation of chain-of-thought prompting is that it relies entirely on parametric knowledge — knowledge stored in the model's weights. ReAct addresses this by allowing the model to gather information dynamically from external sources.

When the model reasons about a question and realizes it lacks information, it can issue a search action to retrieve relevant facts. The observation (retrieved text) is then incorporated into the context for subsequent reasoning steps. This fundamentally differs from pure chain-of-thought approaches where all reasoning must flow from the model's existing knowledge.

### 3. Error Detection and Recovery

One advantage of the ReAct paradigm is that it allows models to detect and recover from reasoning errors mid-trajectory. Because the model alternates between reasoning and observation, it can:

- Notice when a search result does not match expectations
- Update its hypothesis based on new evidence
- Backtrack and try a different approach when initial strategies fail

This is demonstrated on HotpotQA, where ReAct traces show the model explicitly correcting its initial interpretation based on retrieved evidence.

## Benchmarks and Results

### HotpotQA (Multi-hop Question Answering)
- ReAct: 35.1 EM (exact match) vs Chain-of-Thought alone: 29.4
- ReAct + Chain-of-Thought: 36.8 EM
- The improvement comes from the ability to retrieve specific facts needed for multi-hop reasoning

### FEVER (Fact Verification)
- ReAct: 64.9 vs Chain-of-Thought: 56.3 vs Act-only (no reasoning): 58.9
- The combination of reasoning and action significantly outperforms either alone

### ALFWorld (Text-based Interactive Environment)
- ReAct achieves 71% success rate vs BUTLER (imitation learning): 37%
- The model can handle novel situations not seen in the few-shot examples by reasoning about the environment

### WebShop (Online Shopping)
- ReAct achieves 40.4% success vs rule-based methods (~9%) and imitation learning (~28%)

## The Think-Act Loop

The paper establishes what has become known as the "think-act loop" or "ReAct loop" that underlies most modern agentic AI systems:

1. Model receives task description and context
2. Model generates a thought (reasoning about current state)
3. Model issues a structured action call
4. Environment/tool executes the action
5. Observation (result) is appended to context
6. Return to step 2 until task complete

This pattern has been adopted by virtually every subsequent agentic framework including AutoGPT, BabyAGI, LangChain agents, and the four-role architecture in Session 6/7 of this course.

## Comparison with Prior Approaches

| Approach | Reasoning | Actions | External Info |
|----------|-----------|---------|--------------|
| Standard prompting | No | No | No |
| Chain-of-thought | Yes | No | No |
| Act-only | No | Yes | Yes |
| ReAct | Yes | Yes | Yes |

The key insight is that reasoning and action are complementary: reasoning helps determine which actions to take and how to interpret results, while actions ground reasoning in real information rather than potentially incorrect parametric knowledge.

## Limitations

- Performance depends heavily on the quality of the few-shot examples provided
- The model can still hallucinate even when the correct information has been retrieved
- Long trajectories may exceed context window limits
- No mechanism for parallel exploration of multiple reasoning paths (addressed by later work like Tree-of-Thought)
