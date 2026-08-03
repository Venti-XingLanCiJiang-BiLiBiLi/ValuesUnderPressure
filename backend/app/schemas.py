from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


__all__ = [
    "AnswersResponse",
    "AnswerHistoryEntry",
    "ConflictItem",
    "CreateSessionRequest",
    "CreateSessionResponse",
    "DimensionScore",
    "QuestionResponse",
    "ResultResponse",
    "SubmitAnswerRequest",
    "SubmitAnswerResponse",
]


class CreateSessionRequest(BaseModel):
    length: int = Field(default=50, ge=10, le=120, description="试卷题量，默认 50")
    dimensions: Optional[List[str]] = Field(
        default=None, description="仅覆盖指定维度，默认覆盖全部 10 个核心维度"
    )


class CreateSessionResponse(BaseModel):
    session_id: str
    question_count: int


class QuestionResponse(BaseModel):
    question_id: str
    content: str
    type: str
    index: int
    total: int


class SubmitAnswerRequest(BaseModel):
    question_id: str
    answer: str
    duration: Optional[int] = Field(default=None, ge=0)

    @field_validator("answer")
    @classmethod
    def validate_answer(cls, v: str) -> str:
        if v not in ("Y", "N"):
            raise ValueError("answer 只能为 'Y' 或 'N'")
        return v


class AnswerHistoryEntry(BaseModel):
    """答案修改历史记录。"""

    question_id: str
    old_answer: str
    new_answer: str
    changed_at: str


class SubmitAnswerResponse(BaseModel):
    status: str
    answered_count: int
    total: int
    completed: bool
    answer_history: List[AnswerHistoryEntry] = Field(
        default_factory=list,
        description="本次会话的答案修改历史（多次提交时累计返回）",
    )


class AnswersResponse(BaseModel):
    """当前答案 + 修改历史（docs/API.md 答题修改规则）。"""

    session_id: str
    answers: Dict[str, str]
    answer_history: List[AnswerHistoryEntry]


class DimensionScore(BaseModel):
    dimension: str
    name: str
    score: float
    tendency: str
    description: str
    consistency: Optional[float]
    question_count: int
    confidence: float  # 0-1，维度级可信度


class ConflictItem(BaseModel):
    dimensions: List[str]
    names: List[str]
    description: str


class ResultResponse(BaseModel):
    session_id: str
    completed: bool
    answered_count: int
    total: int
    dimensions: Dict[str, DimensionScore]
    confidence: float
    conflicts: List[ConflictItem]
    uncertain_dimensions: List[str]
