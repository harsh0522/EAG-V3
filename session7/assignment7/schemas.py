from __future__ import annotations
from datetime import datetime, timezone, timedelta
IST = timezone(timedelta(hours=5, minutes=30))
from typing import Literal
from pydantic import BaseModel, Field, ConfigDict, model_validator


class MemoryItem(BaseModel):
    id: str
    kind: Literal["fact", "preference", "tool_outcome", "scratchpad"]
    keywords: list[str] = Field(default_factory=list)
    descriptor: str
    value: dict = Field(default_factory=dict)
    artifact_id: str | None = None
    embedding: list[float] | None = None  # S7: FAISS vector, 768-dim
    source: str
    run_id: str
    goal_id: str | None = None
    confidence: float = 1.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(IST))
    score: float = 0.0  # transient: set by memory.read(), not persisted


class Artifact(BaseModel):
    id: str  # "art:<sha256-prefix>"
    content_type: str
    size_bytes: int
    source: str
    descriptor: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(IST))


class Goal(BaseModel):
    id: str  # assigned by outer loop as "g1", "g2", ...
    text: str
    done: bool = False
    attach_artifact_id: str | None = None


class Observation(BaseModel):
    goals: list[Goal]


class ToolCall(BaseModel):
    name: str
    arguments: dict


class DecisionOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer: str | None = None
    tool_call: ToolCall | None = None

    @model_validator(mode="after")
    def exactly_one(self) -> "DecisionOutput":
        if (self.answer is None) == (self.tool_call is None):
            raise ValueError("DecisionOutput must populate exactly one of answer / tool_call")
        return self
