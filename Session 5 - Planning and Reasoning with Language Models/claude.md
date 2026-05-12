Build a Python project named ai-prompt-builder-evaluator.

Create these files: main.py, models.py, gateway_client.py, prompts.py, evaluator.py, pyproject.toml, tests/sample_inputs.json

Project goal:
User gives a rough project idea from CLI. The app runs 4 LLM steps and returns a final optimized prompt with evaluation scores.

Tech requirements:
- Use Python and uv for package management
- Use Pydantic for all input and output validation
- All LLM calls must go through gateway_client.py using the LLM Gateway at http://localhost:8100
- Do not use LangChain or any orchestration framework
- Do not call any provider API directly
- All LLM responses must be JSON only

gateway_client.py:
  Use this exact code:

  import os, json, httpx
  from typing import Any

  DEFAULT_URL = os.getenv("LLM_GATEWAY_V2_URL", "http://localhost:8100")

  class LLM:
      def __init__(self, base_url=DEFAULT_URL, timeout=600):
          self.base_url = base_url.rstrip("/")
          self.timeout = timeout

      def chat(self, prompt=None, *, system=None, provider=None,
               model=None, max_tokens=2048, temperature=0.7):
          body = {"prompt": prompt, "system": system, "provider": provider,
                  "model": model, "max_tokens": max_tokens,
                  "temperature": temperature, "stream": False}
          body = {k: v for k, v in body.items() if v is not None}
          r = httpx.post(f"{self.base_url}/v1/chat", json=body, timeout=self.timeout)
          r.raise_for_status()
          return r.json()

  def call_llm(system_prompt: str, user_message: str) -> str:
      result = LLM().chat(prompt=user_message, system=system_prompt)
      return result["text"]

Pydantic models in models.py:

  ProjectIdeaInput:
    - project_idea: str
    - target_user: Optional[str]
    - constraints: List[str]

  PromptReview:
    - explicit_reasoning: bool
    - structured_output: bool
    - tool_separation: bool
    - conversation_loop: bool
    - instructional_framing: bool
    - internal_self_checks: bool
    - reasoning_type_awareness: bool
    - fallbacks: bool
    - overall_clarity: str

  ImprovedPromptOutput:
    - original_idea: str
    - reasoning: str          ← the model must explain its thought process here
    - generated_prompt: str
    - first_review: PromptReview
    - weaknesses_found: List[str]
    - improved_prompt: str
    - final_review: PromptReview
    - self_check: str
    - confidence: float = Field(ge=0.0, le=1.0)   ← Pydantic validated field

4 LLM steps in evaluator.py:

Step 1 - prompt_builder:
  system: You are a Prompt Builder Agent. Convert the rough idea into a strong implementation-ready LLM prompt. Think step by step. Return only valid JSON with keys: generated_prompt, reasoning, reasoning_type, included_features, confidence.
  user: the raw project idea

Step 2 - prompt_evaluator:
  system: You are a Prompt Evaluator. Score the prompt on 8 criteria. Return only valid JSON with keys: explicit_reasoning, structured_output, tool_separation, conversation_loop, instructional_framing, internal_self_checks, reasoning_type_awareness, fallbacks (all booleans), overall_clarity (string).
  user: the generated_prompt from step 1

Step 3 - prompt_improver:
  system: You are a Prompt Improver. Fix all false criteria. Think step by step. Return only valid JSON with keys: weaknesses_found (list), improved_prompt (string), reasoning (string), confidence (float).
  user: the generated_prompt + first_review JSON

Step 4 - prompt_re_evaluator:
  system: Same as Step 2.
  user: the improved_prompt from step 3

evaluator.py workflow:
  1. Validate input with ProjectIdeaInput
  2. Call prompt_builder → parse JSON → extract generated_prompt and reasoning
  3. Call prompt_evaluator → parse JSON → validate as PromptReview
  4. Call prompt_improver → parse JSON → extract improved_prompt, weaknesses_found, reasoning
  5. Call prompt_re_evaluator → parse JSON → validate as PromptReview
  6. If JSON parsing fails at any step → retry once with: "Return only valid JSON, no extra text."
  7. Set self_check: if all final_review booleans are true write "All 8 criteria passed." else list which failed
  8. Build and return ImprovedPromptOutput as formatted JSON

main.py:
  - Accept project idea via input()
  - Pass to evaluator workflow
  - Print final JSON to terminal

pyproject.toml:
  - name: ai-prompt-builder-evaluator
  - dependencies: pydantic, httpx

tests/sample_inputs.json:
  Add 2 sample project ideas for testing