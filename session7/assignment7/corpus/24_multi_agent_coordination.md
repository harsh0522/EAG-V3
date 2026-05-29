# Multi-Agent Coordination

## Problem Statement

Multi-agent systems distribute work across specialized agents to improve throughput and capability coverage. Without structured coordination, agents produce conflicting outputs, duplicate work, create race conditions on shared resources, and fail to synthesize their individual results into coherent final outputs.

## Solution / Pattern

Use an orchestrator-worker pattern for multi-agent coordination. A single orchestrator agent decomposes the task, assigns sub-tasks to specialized worker agents, monitors completion, and synthesizes results. Worker agents operate independently without knowledge of other workers' tasks, preventing cross-contamination of context and simplifying debugging.

Communication between agents should pass through a structured message queue rather than direct model-to-model calls. This decouples agent lifecycles, allows async execution, and provides a durable audit log of all inter-agent messages.

## Key Details

- The orchestrator should decompose tasks into sub-tasks with explicit deliverable specifications; vague sub-tasks like "research the topic" produce unpredictable outputs that are difficult to synthesize.
- Assign each sub-task a unique task ID and thread all downstream messages (status updates, results, errors) with this ID; without task IDs, correlating results with sub-tasks becomes unreliable as the number of concurrent workers grows.
- Set a timeout for each sub-task; workers that exceed their timeout should be terminated and the orchestrator notified, which can then decide to retry, reassign, or degrade gracefully.
- Do not share mutable state between worker agents; all inter-agent communication should be message-passing with immutable messages; shared mutable state creates race conditions that are nearly impossible to debug in async multi-agent systems.
- Limit worker agents to 3–5 specialized capabilities each; highly specialized agents are easier to test and more reliable than general-purpose agents given broad tool access.
- Use consensus (majority agreement from 3 independent workers) only for high-stakes decisions; for routine sub-tasks, consensus adds 3x cost and latency with marginal quality improvement.
