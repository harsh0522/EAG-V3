# Agent Termination Conditions

## Problem Statement

Agents without well-defined termination conditions either terminate too early (returning incomplete results) or too late (consuming excessive resources on tasks that cannot succeed). Both failure modes erode user trust and create unpredictable costs.

## Solution / Pattern

Define termination conditions in three categories: success conditions, graceful failure conditions, and resource limit conditions. A success condition is met when the agent produces an output that satisfies the original task specification, verified by a completion checker function or model call. A graceful failure condition is met when the agent determines that the task cannot be completed with available tools, information, or permissions, and it should return an explicit "cannot complete" response with a reason. A resource limit condition is met when the agent exceeds predefined limits on iterations, tokens, time, or cost.

Encode all three termination categories in the agent loop's control flow, not just in the model's prompt. Model-only termination logic is unreliable; the model may fail to recognize when it is stuck or may continue generating despite resource exhaustion.

## Key Details

- Set a maximum of 25 tool-use iterations per agent session as a hard limit enforced at the runtime layer; empirically, tasks requiring more than 20 tool calls rarely complete successfully and are more likely stuck in a loop.
- Define a maximum session cost budget (e.g., $0.50 per session) and check running cost against this budget before each LLM call; halt and return a graceful failure if the budget would be exceeded.
- Implement a progress detector: if the last 3 tool call results are identical to results seen earlier in the session, the agent is looping — terminate immediately and log the loop signature for investigation.
- The completion checker should be a separate, lightweight model call with a simple binary prompt: "Has the following agent output fully satisfied the user's request? Answer yes or no." This adds one small model call but significantly reduces false terminations.
- Always return a structured termination reason in the agent response: `{"status": "success|failure|timeout|budget_exceeded", "reason": "..."}` so orchestrating systems can handle different outcomes appropriately.
