# Agent Loop Design

## Problem Statement

Agent loops that allow arbitrary numbers of tool calls per iteration create ambiguous execution states. When a step that invokes three tools simultaneously partially fails, it is unclear which tools completed, which need to be retried, and whether the completed tools produced side effects that make retry unsafe.

## Solution / Pattern

Agent loops must enforce atomic decision making: exactly one tool call or one answer per iteration. Allowing multiple tool calls per step creates ambiguous states where partial failures cannot be retried cleanly. The agent should observe, reason about its next single action, execute that action, receive the result, and then observe again — this is the canonical observe-reason-act cycle that makes agent behavior auditable and recoverable.

Structure the agent loop with explicit phases: a planning phase where the model reasons about what to do next (in a scratchpad or chain-of-thought), a tool selection phase where it nominates exactly one tool and its arguments, an execution phase where the runtime invokes the tool, and an integration phase where the result is added to the context.

## Key Details

- Enforce the one-tool-per-step constraint at the runtime layer, not just in the prompt; if the model attempts to output multiple tool calls in a single response, parse only the first and discard the rest, then log the violation.
- Set a hard maximum of 25 iterations per agent session; sessions that exceed this are almost always stuck in a loop or chasing an unachievable goal, and continued execution wastes resources without producing value.
- Track the sequence of tool calls in each session as a structured log; repeated sequences of the same 2–3 tool calls are the primary signal for loop detection.
- Include the iteration count in the system prompt or a dedicated field visible to the model; models given awareness of their remaining iteration budget make better prioritization decisions.
- Each tool call should be idempotent wherever possible; design tools so that calling them twice with the same arguments produces the same result and no additional side effects, enabling safe retry.
- After 5 consecutive tool calls without producing a user-visible output, inject a "check-in" prompt that asks the model whether it is still making progress toward the original goal.
