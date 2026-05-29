# Model Routing Strategies

## Problem Statement

Using the most powerful (and expensive) model for every request is cost-prohibitive at scale. Using the cheapest model for all requests degrades quality on complex tasks. Production systems need a routing strategy that matches request complexity to the appropriate model tier.

## Solution / Pattern

Model routing classifies incoming requests by complexity and routes them to the cheapest model capable of handling them at acceptable quality. A routing classifier (a small, fast model or a rule-based system) evaluates each request before it is sent to a generation model. Simple, well-defined tasks (classification, extraction, formatting) are routed to small models. Complex reasoning, multi-step tasks, and tasks requiring broad knowledge are routed to large models.

Implement routing as a cascade: first attempt the request with a small model, evaluate confidence using output probability scores or a secondary verifier, and escalate to a larger model only if confidence is below the threshold.

## Key Details

- Set the escalation threshold at a confidence score of 0.75; requests below this threshold are escalated to the next model tier. This threshold balances escalation rate (cost) against quality; tuning should be done on a task-specific evaluation set.
- Track escalation rate as a key operational metric; escalation rates above 30% indicate the routing classifier is under-specifying the small model's capability and the threshold or routing rules need adjustment.
- Small model routing is most effective for tasks with high query volume and predictable structure; for rare, complex tasks, the routing overhead is not worth the savings.
- Maintain separate prompt versions for each model tier; prompts optimized for a large model with long chain-of-thought often perform worse on small models than purpose-written concise prompts.
- Include a bypass path for requests explicitly tagged as high-complexity by the application layer (e.g., user-specified "thorough analysis" mode); never route these through the small model tier.
- Measure quality difference between routed and unrouted traffic on a 5% sample by comparing both outputs with an LLM judge; the quality gap should be less than 5% on your task metric.
