import json
from models import ProjectIdeaInput, PromptReview, ImprovedPromptOutput
from gateway_client import call_llm
from logger import RunLogger
from prompts import (
    PROMPT_BUILDER_SYSTEM,
    PROMPT_EVALUATOR_SYSTEM,
    PROMPT_IMPROVER_SYSTEM,
    RETRY_SUFFIX,
)


_CRITERION_PATCHES = {
    "conversation_loop": "If anything is unclear or ambiguous, ask clarifying questions before proceeding.",
    "internal_self_checks": "Before giving your final answer, review your own output and fix any errors or gaps.",
    "fallbacks": "If you cannot complete any part of the task, clearly state what is missing and provide the best partial answer you can.",
    "explicit_reasoning": "Think step by step and explain your reasoning before giving the final answer.",
    "structured_output": "Return your response in structured JSON format.",
    "instructional_framing": "You are an expert assistant.",
    "reasoning_type_awareness": "Use deductive reasoning to analyze the problem and apply causal reasoning when identifying root causes.",
    "tool_separation": "Clearly separate distinct capabilities (e.g. search, compute, retrieve) as named steps.",
}


def _patch_criteria(prompt: str, review: dict) -> str:
    additions = [
        sentence
        for criterion, sentence in _CRITERION_PATCHES.items()
        if not review.get(criterion, True) and sentence.lower() not in prompt.lower()
    ]
    if additions:
        prompt = prompt.rstrip() + "\n\n" + " ".join(additions)
    return prompt


def _parse_json(raw: str, system: str, user: str, log: RunLogger) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        retry_raw = call_llm(system, user + RETRY_SUFFIX)
        log.steps[-1]["retried"] = True
        return json.loads(retry_raw)


def run_evaluator(idea: str, target_user: str | None = None, constraints: list[str] | None = None) -> str:
    log = RunLogger(idea)

    # Pydantic validation #1 — ProjectIdeaInput (user input)
    raw_constraints = constraints  # capture before the `or []` default
    input_data = ProjectIdeaInput(
        project_idea=idea,
        target_user=target_user,
        constraints=constraints or [],
    )
    log.log_pydantic(0, "ProjectIdeaInput", "User Input", {
        "project_idea": idea,
        "target_user": target_user,
        "constraints": raw_constraints,
    }, input_data.model_dump())

    # Step 1 - prompt_builder
    step1_user = input_data.project_idea
    log.begin_step(1, "Prompt Builder", PROMPT_BUILDER_SYSTEM, step1_user)
    step1_raw = call_llm(PROMPT_BUILDER_SYSTEM, step1_user)
    step1 = _parse_json(step1_raw, PROMPT_BUILDER_SYSTEM, step1_user, log)
    log.end_step(step1_raw, step1)
    generated_prompt = step1["generated_prompt"]
    reasoning = step1["reasoning"]
    confidence_raw = float(step1.get("confidence", 0.7))

    # Step 2 - prompt_evaluator
    step2_user = generated_prompt
    log.begin_step(2, "Prompt Evaluator", PROMPT_EVALUATOR_SYSTEM, step2_user)
    step2_raw = call_llm(PROMPT_EVALUATOR_SYSTEM, step2_user)
    step2 = _parse_json(step2_raw, PROMPT_EVALUATOR_SYSTEM, step2_user, log)
    log.end_step(step2_raw, step2)
    # Pydantic validation #2 — PromptReview (first evaluation)
    first_review = PromptReview(**step2)
    log.log_pydantic(2, "PromptReview", "First Evaluation", step2, first_review.model_dump())

    # Step 3 - prompt_improver
    step3_user = f"Prompt:\n{generated_prompt}\n\nFirst Review:\n{json.dumps(step2, indent=2)}"
    log.begin_step(3, "Prompt Improver", PROMPT_IMPROVER_SYSTEM, step3_user)
    step3_raw = call_llm(PROMPT_IMPROVER_SYSTEM, step3_user)
    step3 = _parse_json(step3_raw, PROMPT_IMPROVER_SYSTEM, step3_user, log)
    log.end_step(step3_raw, step3)
    improved_prompt = _patch_criteria(step3["improved_prompt"], step2)
    weaknesses_found = step3["weaknesses_found"]
    improver_reasoning = step3.get("reasoning", reasoning)
    confidence_raw = float(step3.get("confidence", confidence_raw))

    # Step 4 - prompt_re_evaluator
    step4_user = improved_prompt
    log.begin_step(4, "Re-Evaluator", PROMPT_EVALUATOR_SYSTEM, step4_user)
    step4_raw = call_llm(PROMPT_EVALUATOR_SYSTEM, step4_user)
    step4 = _parse_json(step4_raw, PROMPT_EVALUATOR_SYSTEM, step4_user, log)
    log.end_step(step4_raw, step4)
    # Pydantic validation #3 — PromptReview (final evaluation)
    final_review = PromptReview(**step4)
    log.log_pydantic(4, "PromptReview", "Final Evaluation", step4, final_review.model_dump())

    # self_check
    field_names = [
        "explicit_reasoning", "structured_output", "tool_separation",
        "conversation_loop", "instructional_framing", "internal_self_checks",
        "reasoning_type_awareness", "fallbacks",
    ]
    review_values = [getattr(final_review, f) for f in field_names]
    if all(review_values):
        self_check = "All 8 criteria passed."
    else:
        failed = [n for n, v in zip(field_names, review_values) if not v]
        self_check = "Failed criteria: " + ", ".join(failed)

    clamped_confidence = min(max(confidence_raw, 0.0), 1.0)
    output = ImprovedPromptOutput(
        original_idea=input_data.project_idea,
        reasoning=improver_reasoning,
        generated_prompt=generated_prompt,
        first_review=first_review,
        weaknesses_found=weaknesses_found,
        improved_prompt=improved_prompt,
        final_review=final_review,
        self_check=self_check,
        confidence=clamped_confidence,
    )
    # Pydantic validation #4 — ImprovedPromptOutput (final assembly)
    raw_output_fields = {
        "original_idea": input_data.project_idea,
        "reasoning": improver_reasoning,
        "generated_prompt": generated_prompt,
        "first_review": first_review.model_dump(),
        "weaknesses_found": weaknesses_found,
        "improved_prompt": improved_prompt,
        "final_review": final_review.model_dump(),
        "self_check": self_check,
        "confidence (raw, before clamp)": confidence_raw,
        "confidence (after clamp to [0,1])": clamped_confidence,
    }
    log.log_pydantic(5, "ImprovedPromptOutput", "Final Assembly", raw_output_fields, output.model_dump())

    final_json = output.model_dump_json(indent=2)
    log_path = log.write_html(final_json)
    print(f"\nLog saved → {log_path}")

    return final_json
