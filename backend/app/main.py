"""
aPersonalityTest 后端服务

严格对齐仓库内文档定义的开发目标:
  docs/TestDesign.md      -> 会话生命周期 (创建会话 -> 分层抽题 -> 作答 -> 计分 -> 结果)
  docs/API.md             -> REST 接口形状
  docs/QuestionSelection.md -> 分层随机组卷，不允许全局随机抽题
  docs/ScoringAlgorithm.md   -> 累加 + 归一化 + 一致性
  docs/ResultInterpretation.md -> 倾向描述 / 矛盾分析 / 不确定性，不做人格定性判断
  docs/DataValidation.md  -> 题库加载时的 schema/权重校验
  docs/DatabaseSchema.md  -> sessions/answers/results 持久化
"""

from __future__ import annotations

import json
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .dimensions import DIMENSIONS
from .question_bank import QuestionBank, load_question_bank
from .schemas import (
    ConflictItem,
    CreateSessionRequest,
    CreateSessionResponse,
    DimensionScore,
    QuestionResponse,
    ResultResponse,
    SubmitAnswerRequest,
    SubmitAnswerResponse,
)
from .scoring import score_session
from .selection import build_test

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("apersonalitytest")

app = FastAPI(
    title="aPersonalityTest API",
    description="基于 Y/N 极端情境题的价值排序测试后端",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_bank: QuestionBank | None = None


def get_bank() -> QuestionBank:
    global _bank
    if _bank is None:
        _bank = load_question_bank()
    return _bank


@app.on_event("startup")
def on_startup() -> None:
    db.init_db()
    bank = get_bank()
    logger.info(
        "题库就绪: 来源=%s 有效题数=%d 无效题数=%d",
        bank.source,
        len(bank.questions),
        len(bank.invalid),
    )


@app.get("/api/health")
def health():
    bank = get_bank()
    return {
        "status": "ok",
        "question_bank_source": bank.source,
        "active_questions": len(bank.active_questions()),
        "invalid_questions": len(bank.invalid),
    }


@app.get("/api/dimensions")
def list_dimensions():
    return {
        dim: {"name": meta["name"], "description": meta["description"], "direction": meta["direction"]}
        for dim, meta in DIMENSIONS.items()
    }


# ---------------------------------------------------------------------------
# 测试流程接口 (docs/API.md)
# ---------------------------------------------------------------------------


@app.post("/api/test/session", response_model=CreateSessionResponse)
def create_session(req: CreateSessionRequest):
    bank = get_bank()
    questions = build_test(bank, length=req.length, dimensions=req.dimensions)
    if not questions:
        raise HTTPException(500, "题库为空或无法生成试卷，请检查题库文件")

    session_id = db.create_session(
        question_version=bank.version(),
        length=len(questions),
        dimensions=req.dimensions or [],
        question_ids=[q.id for q in questions],
    )
    return CreateSessionResponse(session_id=session_id, question_count=len(questions))


def _session_or_404(session_id: str):
    row = db.get_session(session_id)
    if row is None:
        raise HTTPException(404, "测试会话不存在")
    return row


def _session_questions(row) -> list:
    bank = get_bank()
    ids = json.loads(row["question_ids_json"])
    return [bank.get(qid) for qid in ids if bank.get(qid) is not None]


@app.get("/api/test/session/{session_id}/question", response_model=QuestionResponse)
def next_question(session_id: str):
    row = _session_or_404(session_id)
    questions = _session_questions(row)
    idx = row["current_index"]

    if idx >= len(questions):
        raise HTTPException(409, "本次测试已完成，请调用结果接口")

    q = questions[idx]
    return QuestionResponse(
        question_id=q.id, content=q.content, type=q.type, index=idx, total=len(questions)
    )


@app.post("/api/test/session/{session_id}/answer", response_model=SubmitAnswerResponse)
def submit_answer(session_id: str, req: SubmitAnswerRequest):
    row = _session_or_404(session_id)
    questions = _session_questions(row)
    ids = [q.id for q in questions]

    if req.question_id not in ids:
        raise HTTPException(400, "question_id 不属于本次测试会话")

    idx = row["current_index"]
    if idx < len(questions) and questions[idx].id == req.question_id:
        # 正常顺序作答，指针前移
        db.advance_pointer(session_id, idx + 1)
        new_idx = idx + 1
    else:
        # 允许对已出现过的题目进行补答/修改，不移动指针
        new_idx = idx

    db.save_answer(session_id, req.question_id, req.answer, req.duration)

    answers = db.get_answers(session_id)
    completed = new_idx >= len(questions)
    if completed:
        db.mark_completed(session_id)

    return SubmitAnswerResponse(
        status="ok",
        answered_count=len(answers),
        total=len(questions),
        completed=completed,
    )


@app.get("/api/test/session/{session_id}/result", response_model=ResultResponse)
def get_result(session_id: str):
    row = _session_or_404(session_id)
    questions = _session_questions(row)
    answers = db.get_answers(session_id)

    if not answers:
        raise HTTPException(409, "尚未作答任何题目，无法生成结果")

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
        )
        for dim, r in result.dimensions.items()
    }

    db.save_results(
        session_id,
        {
            dim: {"score": r.score, "consistency": r.consistency}
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
