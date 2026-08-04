"""测试流程接口（docs/API.md）：会话生命周期。

- `POST /api/test/session` — 创建测试会话（分层组卷）
- `GET  /api/test/session/{id}/question` — 取下一题
- `POST /api/test/session/{id}/answer` — 提交 Y/N 答案（允许修改，记录历史）
- `GET  /api/test/session/{id}/answers` — 当前答案与修改历史
- `GET  /api/test/session/{id}/result` — 拿结果（10 维度 + 矛盾分析 + 置信度）
"""
from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Request

from .. import db
from ..bank_state import get_bank
from ..rate_limit import limiter
from ..schemas import (
    AnswerHistoryEntry,
    AnswersResponse,
    ConflictItem,
    CreateSessionRequest,
    CreateSessionResponse,
    DimensionScore,
    QuestionResponse,
    ResultResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
)
from ..scoring import score_session
from ..selection import build_test

router = APIRouter()


@router.post("/api/test/session", response_model=CreateSessionResponse)
@limiter.limit("10/minute")
async def create_session(request: Request, req: CreateSessionRequest):
    bank = get_bank()
    questions = build_test(bank, length=req.length, dimensions=req.dimensions)
    if not questions:
        raise HTTPException(500, "题库为空或无法生成试卷，请检查题库文件")

    session_id = await db.create_session(
        question_version=bank.version(),
        length=len(questions),
        dimensions=req.dimensions or [],
        question_ids=[q.id for q in questions],
    )
    return CreateSessionResponse(session_id=session_id, question_count=len(questions))


async def _session_or_404(session_id: str):
    row = await db.get_session(session_id)
    if row is None:
        raise HTTPException(404, "测试会话不存在")
    return row


def _session_questions(row) -> list:
    bank = get_bank()
    ids = json.loads(row["question_ids_json"])
    return [bank.get(qid) for qid in ids if bank.get(qid) is not None]


@router.get("/api/test/session/{session_id}/question", response_model=QuestionResponse)
@limiter.limit("120/minute")
async def next_question(request: Request, session_id: str):
    row = await _session_or_404(session_id)
    questions = _session_questions(row)
    idx = row["current_index"]

    if idx >= len(questions):
        raise HTTPException(409, "本次测试已完成，请调用结果接口")

    q = questions[idx]
    return QuestionResponse(
        question_id=q.id, content=q.content, type=q.type, index=idx, total=len(questions)
    )


@router.post("/api/test/session/{session_id}/answer", response_model=SubmitAnswerResponse)
@limiter.limit("60/minute")
async def submit_answer(request: Request, session_id: str, req: SubmitAnswerRequest):
    row = await _session_or_404(session_id)
    questions = _session_questions(row)
    ids = [q.id for q in questions]

    if req.question_id not in ids:
        raise HTTPException(400, "question_id 不属于本次测试会话")

    idx = row["current_index"]
    if idx < len(questions) and questions[idx].id == req.question_id:
        # 正常顺序作答，指针前移
        await db.advance_pointer(session_id, idx + 1)
        new_idx = idx + 1
    else:
        # 允许对已出现过的题目进行补答/修改，不移动指针
        new_idx = idx

    # 允许修改已提交的答案（价值观测试不是考试）：
    # 修改不改变答题进度，但必须记录修改历史 answer_history。
    old_answer = await db.get_answer(session_id, req.question_id)
    await db.save_answer(session_id, req.question_id, req.answer, req.duration)
    if old_answer is not None and old_answer != req.answer:
        await db.record_answer_change(session_id, req.question_id, old_answer, req.answer)

    answers = await db.get_answers(session_id)
    completed = new_idx >= len(questions)
    if completed:
        await db.mark_completed(session_id)

    return SubmitAnswerResponse(
        status="ok",
        answered_count=len(answers),
        total=len(questions),
        completed=completed,
        answer_history=[
            AnswerHistoryEntry(**h) for h in await db.get_answer_history(session_id)
        ],
    )


@router.get("/api/test/session/{session_id}/answers", response_model=AnswersResponse)
@limiter.limit("120/minute")
async def get_answers(request: Request, session_id: str):
    """返回当前答案与修改历史（答题修改规则见 docs/API.md）。"""
    await _session_or_404(session_id)
    return AnswersResponse(
        session_id=session_id,
        answers=await db.get_answers(session_id),
        answer_history=[
            AnswerHistoryEntry(**h) for h in await db.get_answer_history(session_id)
        ],
    )


@router.get("/api/test/session/{session_id}/result", response_model=ResultResponse)
@limiter.limit("120/minute")
async def get_result(request: Request, session_id: str):
    row = await _session_or_404(session_id)
    questions = _session_questions(row)
    answers = await db.get_answers(session_id)

    # 结果必须基于完整作答：未完成全部题目时返回 409，避免把部分作答
    # 当作完整画像输出（归一化、一致性都需要完整样本才有效）。
    if len(answers) < len(questions):
        raise HTTPException(
            409,
            f"测试尚未完成：已作答 {len(answers)}/{len(questions)}，"
            "请完成所有题目后再获取结果",
        )

    result = score_session(questions, answers)

    dimension_payload = {
        dim: DimensionScore(
            dimension=r.dimension,
            name=r.name,
            score=r.score,
            tendency=r.tendency,
            description=r.description,
            consistency=r.consistency,
            question_count=r.question_count,
            confidence=r.confidence,
        )
        for dim, r in result.dimensions.items()
    }

    await db.save_results(
        session_id,
        {
            dim: {
                "score": r.score,
                "consistency": r.consistency,
                "confidence": r.confidence,
            }
            for dim, r in result.dimensions.items()
        },
        result.confidence,
    )

    return ResultResponse(
        session_id=session_id,
        completed=len(answers) >= len(questions),
        answered_count=len(answers),
        total=len(questions),
        dimensions=dimension_payload,
        confidence=result.confidence,
        conflicts=[ConflictItem(**c) for c in result.conflicts],
        uncertain_dimensions=result.uncertain_dimensions,
    )
