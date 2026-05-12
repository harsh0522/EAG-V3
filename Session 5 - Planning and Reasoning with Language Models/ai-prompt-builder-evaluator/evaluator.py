import json
from models import ProjectIdeaInput, PromptReview, ImprovedPromptOutput
from gateway_client import call_llm
from prompts import (
    PROMPT_BUILDER_SYSTEM,
    PROMPT_EVALUATOR_SYSTEM,
    PROMPT_IMPROVER_SYSTEM,
    RETRY_SUFFIX,
)


def _parse_json(raw: str, system: str, user: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        retry_raw = call_llm(system, user + RETRY_SUFFIX)
        return json.loads(retry_raw)


def run_evaluator(idea: str, target_user: str | None = None, constraints: list[str] | None = None) -> str:
    input_data = ProjectIdeaInput(
        project_idea=idea,
        target_user=target_user,
        constraints=constraints or [],
    )

    # Step 1 - prompt_builder
    step1_user = input_data.project_idea
    step1_raw = call_llm(PROMPT_BUILDER_SYSTEM, step1_user)
    step1 = _parse_json(step1_raw, PROMPT_BUILDER_SYSTEM, step1_user)
    generated_prompt = step1["generated_prompt"]
    reasoning = step1["reasoning"]
    confidence_raw = float(step1.get("confidence", 0.7))

    # Step 2 - prompt_evaluator
    step2_user = generated_prompt
    step2_raw = call_llm(PROMPT_EVALUATOR_SYSTEM, step2_user)
    step2 = _parse_json(step2_raw, PROMPT_EVALUATOR_SYSTEM, step2_user)
    first_review = PromptReview(**step2)

    # Step 3 - prompt_improver
    step3_user = f"Prompt:\n{generated_prompt}\n\nFirst Review:\n{json.dumps(step2, indent=2)}"
    step3_raw = call_llm(PROMPT_IMPROVER_SYSTEM, step3_user)
    step3 = _parse_json(step3_raw, PROMPT_IMPROVER_SYSTEM, step3_user)
    improved_prompt = step3["improved_prompt"]
    weaknesses_found = step3["weaknesses_found"]
    improver_reasoning = step3.get("reasoning", reasoning)
    confidence_raw = float(step3.get("confidence", confidence_raw))

    # Step 4 - prompt_re_evaluator
    step4_user = improved_prompt
    step4_raw = call_llm(PROMPT_EVALUATOR_SYSTEM, step4_user)
    step4 = _parse_json(step4_raw, PROMPT_EVALUATOR_SYSTEM, step4_user)
    final_review = PromptReview(**step4)

    # self_check
    review_fields = [
        final_review.explicit_reasoning,
        final_review.structured_output,
        final_review.tool_separation,
        final_review.conversation_loop,
        final_review.instructional_framing,
        final_review.internal_self_checks,
        final_review.reasoning_type_awareness,
        final_review.fallbacks,
    ]
    field_names = [
        "explicit_reasoning", "structured_output", "tool_separation",
        "conversation_loop", "instructional_framing", "internal_self_checks",
        "reasoning_type_awareness", "fallbacks",
    ]
    if all(review_fields):
        self_check = "All 8 criteria passed."
    else:
        failed = [name for name, val in zip(field_names, review_fields) if not val]
        self_check = "Failed criteria: " + ", ".join(failed)

    output = ImprovedPromptOutput(
        original_idea=input_data.project_idea,
        reasoning=improver_reasoning,
        generated_prompt=generated_prompt,
        first_review=first_review,
        weaknesses_found=weaknesses_found,
        improved_prompt=improved_prompt,
        final_review=final_review,
        self_check=self_check,
        confidence=min(max(confidence_raw, 0.0), 1.0),
    )

    return output.model_dump_json(indent=2)
