from typing import Optional, List
from pydantic import BaseModel, Field


class ProjectIdeaInput(BaseModel):
    project_idea: str
    target_user: Optional[str] = None
    constraints: List[str] = []


class PromptReview(BaseModel):
    explicit_reasoning: bool
    structured_output: bool
    tool_separation: bool
    conversation_loop: bool
    instructional_framing: bool
    internal_self_checks: bool
    reasoning_type_awareness: bool
    fallbacks: bool
    overall_clarity: str


class ImprovedPromptOutput(BaseModel):
    original_idea: str
    reasoning: str
    generated_prompt: str
    first_review: PromptReview
    weaknesses_found: List[str]
    improved_prompt: str
    final_review: PromptReview
    self_check: str
    confidence: float = Field(ge=0.0, le=1.0)
