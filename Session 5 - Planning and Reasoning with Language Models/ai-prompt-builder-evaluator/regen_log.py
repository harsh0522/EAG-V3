"""
Re-renders latest.html from the last run's final JSON — no LLM or gateway needed.
Run with:  python regen_log.py
"""
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from logger import _render_html, _CRITERIA_DESCRIPTIONS

LOGS_DIR = Path(__file__).parent / "logs"
latest = LOGS_DIR / "latest.html"

if not latest.exists():
    print("No latest.html found. Run python main.py first.")
    sys.exit(1)

html_text = latest.read_text(encoding="utf-8")

# Extract the embedded JSON from the final-json block
match = re.search(r'<pre class="final-json">(.*?)</pre>', html_text, re.DOTALL)
if not match:
    print("Could not find final JSON block in latest.html")
    sys.exit(1)

raw = match.group(1)
raw = raw.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
final = json.loads(raw)

# Reconstruct minimal step objects so the explainer can render properly
first_rev = final.get("first_review", {})
final_rev  = final.get("final_review", {})

steps = [
    {
        "number": 1, "name": "Prompt Builder",
        "system_prompt": "You are a Prompt Builder Agent. Convert the rough idea into a strong implementation-ready LLM prompt. Think step by step. Return only valid JSON with keys: generated_prompt, reasoning, reasoning_type, included_features, confidence.",
        "user_message": final.get("original_idea", ""),
        "raw_response": json.dumps({"generated_prompt": final.get("generated_prompt", ""), "reasoning": final.get("reasoning", ""), "confidence": final.get("confidence", 0.9)}, indent=2),
        "parsed_output": {"generated_prompt": final.get("generated_prompt", ""), "reasoning": final.get("reasoning", "")},
        "retried": False, "duration_ms": 0, "error": None,
    },
    {
        "number": 2, "name": "Prompt Evaluator",
        "system_prompt": "You are a Prompt Evaluator. Score the prompt on 8 criteria. Return only valid JSON with keys: explicit_reasoning, structured_output, tool_separation, conversation_loop, instructional_framing, internal_self_checks, reasoning_type_awareness, fallbacks (all booleans), overall_clarity (string).",
        "user_message": final.get("generated_prompt", ""),
        "raw_response": json.dumps(first_rev, indent=2),
        "parsed_output": first_rev,
        "retried": False, "duration_ms": 0, "error": None,
    },
    {
        "number": 3, "name": "Prompt Improver",
        "system_prompt": "You are a Prompt Improver. Fix all false criteria. Return only valid JSON with keys: weaknesses_found (list), improved_prompt (string), reasoning (string), confidence (float).",
        "user_message": f"Prompt:\n{final.get('generated_prompt','')}\n\nFirst Review:\n{json.dumps(first_rev, indent=2)}",
        "raw_response": json.dumps({"weaknesses_found": final.get("weaknesses_found", []), "improved_prompt": final.get("improved_prompt", ""), "reasoning": final.get("reasoning", ""), "confidence": final.get("confidence", 0.9)}, indent=2),
        "parsed_output": {"weaknesses_found": final.get("weaknesses_found", []), "improved_prompt": final.get("improved_prompt", ""), "reasoning": final.get("reasoning", "")},
        "retried": False, "duration_ms": 0, "error": None,
    },
    {
        "number": 4, "name": "Re-Evaluator",
        "system_prompt": "You are a Prompt Evaluator. Score the prompt on 8 criteria. Return only valid JSON with keys: explicit_reasoning, structured_output, tool_separation, conversation_loop, instructional_framing, internal_self_checks, reasoning_type_awareness, fallbacks (all booleans), overall_clarity (string).",
        "user_message": final.get("improved_prompt", ""),
        "raw_response": json.dumps(final_rev, indent=2),
        "parsed_output": final_rev,
        "retried": False, "duration_ms": 0, "error": None,
    },
]

first_rev = final.get("first_review", {})
final_rev = final.get("final_review", {})

pydantic_events = [
    {
        "step_num": 0, "model_name": "ProjectIdeaInput", "label": "User Input",
        "raw_input": {"project_idea": final.get("original_idea", ""), "target_user": None, "constraints": None},
        "validated_output": {"project_idea": final.get("original_idea", ""), "target_user": None, "constraints": []},
        "coercions": [{"field": "constraints", "kind": "default", "detail": "field was None → default applied: []"}],
    },
    {
        "step_num": 2, "model_name": "PromptReview", "label": "First Evaluation",
        "raw_input": first_rev,
        "validated_output": first_rev,
        "coercions": [],
    },
    {
        "step_num": 4, "model_name": "PromptReview", "label": "Final Evaluation",
        "raw_input": final_rev,
        "validated_output": final_rev,
        "coercions": [],
    },
    {
        "step_num": 5, "model_name": "ImprovedPromptOutput", "label": "Final Assembly",
        "raw_input": {
            "original_idea": final.get("original_idea", ""),
            "reasoning": final.get("reasoning", ""),
            "generated_prompt": final.get("generated_prompt", ""),
            "first_review": first_rev,
            "weaknesses_found": final.get("weaknesses_found", []),
            "improved_prompt": final.get("improved_prompt", ""),
            "final_review": final_rev,
            "self_check": final.get("self_check", ""),
            "confidence (raw, before clamp)": final.get("confidence", 1.0),
            "confidence (after clamp to [0,1])": final.get("confidence", 1.0),
        },
        "validated_output": {k: v for k, v in final.items()},
        "coercions": [],
    },
]

final_json_str = json.dumps(final, indent=2)
new_html = _render_html(
    idea=final.get("original_idea", ""),
    started=datetime.now(),
    steps=steps,
    pydantic_events=pydantic_events,
    final_json=final_json_str,
)

latest.write_text(new_html, encoding="utf-8")
print(f"Regenerated: {latest}")
