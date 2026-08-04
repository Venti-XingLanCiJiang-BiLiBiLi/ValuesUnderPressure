"""
取舍之间 (Values Under Pressure, VUP) 后端服务

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
import os
import threading
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware

# 模块级 logger：handler 在 init_logging()（lifespan 启动时）配置。
# 先在此定义，避免 reload_bank 等函数在 lifespan 之前被调用时 NameError。
logger = logging.getLogger("apersonalitytest")


def init_logging():
    """Configure the application logger based on environment variables.

    - JSON_LOGS=1 enables structured JSON output via pythonjsonlogger.
    - Uses the module-level `apersonalitytest` logger and deduplicates handlers
      across reloads.
    """
    # Remove duplicate handlers on reload, but keep other loggers intact.
    if getattr(logger, "_vup_handlers_cleared", False) is not True:
        logger.handlers.clear()
        logger._vup_handlers_cleared = True

    try:
        if os.environ.get("JSON_LOGS", "0") == "1":
            from pythonjsonlogger import jsonlogger

            handler = logging.StreamHandler()
            fmt = jsonlogger.JsonFormatter(
                "%(asctime)s %(levelname)s %(name)s %(message)s"
            )
            handler.setFormatter(fmt)
        else:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
            )
    except ImportError:
        # Fallback to simple logging if json logger is unavailable
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )

    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger


from . import db
from .dimensions import DIMENSIONS, reload_dimensions
from .question_bank import BucketBank, load_bucket_bank
from .schemas import (
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
from .scoring import score_session
from .selection import build_test

_bank: BucketBank | None = None
_bank_lock = threading.Lock()
# 保留备用：模块级缓存 ADMIN_TOKEN，供后续其它 admin 接口复用。
# 当前 reload_bank 的鉴权在函数内实时读取环境变量（便于测试动态注入）。
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
def get_bank() -> BucketBank:
    global _bank
    if _bank is None:
        new_bank = load_bucket_bank()
        with _bank_lock:
            if _bank is None:
                _bank = new_bank
    return _bank


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Initialize logging early so startup logs follow configured format.
    init_logging()

    db.init_db()
    bank = get_bank()
    logger.info(
        "题库就绪: 版本=%s 索引组数=%d 总题数=%d",
        bank.version(),
        len(bank.groups()),
        bank.total_questions(),
    )
    yield


app = FastAPI(
    title="取舍之间 · Values Under Pressure API",
    description=(
        "取舍之间 (Values Under Pressure, VUP) — "
        "基于 Y/N 极端价值冲突场景的价值观压力测试后端。\n\n"
        "**核心理念**：结果只描述倾向，不做人格定性；允许不同情境下出现矛盾。\n\n"
        "## 模块\n"
        "- `POST /api/test/session` — 创建测试会话（分层组卷）\n"
        "- `GET  /api/test/session/{id}/question` — 取下一题\n"
        "- `POST /api/test/session/{id}/answer` — 提交 Y/N 答案（允许修改已提交答案，记录历史）\n"
        "- `GET  /api/test/session/{id}/answers` — 当前答案与修改历史\n"
        "- `GET  /api/test/session/{id}/result` — 拿结果（10 维度 + 矛盾分析 + 维度置信度）\n"
        "- `GET  /api/dimensions` — 10 个核心维度的元数据\n"
        "- `GET  /api/health` — 服务与题库状态\n\n"
        "接口与数据约定见仓库 `docs/API.md`。"
    ),
    lifespan=lifespan,
)

# Configure CORS from environment for production safety.
# - `CORS_ALLOWED_ORIGINS` can be a comma-separated list of allowed origins.
# - If not set and `ENV` != "production", default to permissive `[*]` for dev.
# Reminder: server-to-server/container internal calls often omit the `Origin`
# header and are not blocked by CORSMiddleware; this preserves docker internal
# inter-service communication.
cors_env = os.environ.get("CORS_ALLOWED_ORIGINS", "")
env_mode = os.environ.get("ENV", "development").lower()
if cors_env:
    # split and strip
    allowed_origins = [o.strip() for o in cors_env.split(",") if o.strip()]
elif env_mode != "production":
    allowed_origins = ["*"]
else:
    # In production, be strict by default. Operators should set CORS_ALLOWED_ORIGINS.
    logging.getLogger("apersonalitytest").warning("CORS_ALLOWED_ORIGINS not set in production; all browser requests will be blocked")
    allowed_origins = []

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    bank = get_bank()
    return {
        "status": "ok",
        "question_bank_version": bank.version(),
        "groups": len(bank.groups()),
        "active_questions": bank.total_questions(),
    }


@app.get("/api/dimensions")
def list_dimensions():
    return {
        dim: {"name": meta["name"], "description": meta["description"], "direction": meta["direction"]}
        for dim, meta in DIMENSIONS.items()
    }


@app.post("/api/admin/reload-bank")
def reload_bank(x_admin_token: str = Header(...)):
    """热更新题库（#14）。需要 X-Admin-Token 请求头鉴权。

    注意：热更新后，已创建的活跃会话可能因题库变化而缺少题目
    （_session_questions 已过滤 None，但文档应明确此行为）。
    """
    token = os.environ.get("ADMIN_TOKEN", "")
    if not token or x_admin_token != token:
        raise HTTPException(403, "Invalid admin token")

    global _bank
    try:
        new_bank = load_bucket_bank()
        with _bank_lock:
            _bank = new_bank
        # 维度元数据与题库同源存放（question-bank/<version>/dimensions.json），
        # 热更新题库时一并重载，保持「题库 + 维度」一致。
        reload_dimensions()
        logger.info(
            "题库热更新成功: version=%s groups=%d active_questions=%d",
            new_bank.version(),
            len(new_bank.groups()),
            new_bank.total_questions(),
        )
        return {
            "ok": True,
            "version": new_bank.version(),
            "groups": len(new_bank.groups()),
            "active_questions": new_bank.total_questions(),
        }
    except Exception as e:
        logger.error("题库热更新失败: %s", e)
        raise HTTPException(500, f"Reload failed: {e}")


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

    # 允许修改已提交的答案（价值观测试不是考试）：
    # 修改不改变答题进度，但必须记录修改历史 answer_history。
    old_answer = db.get_answer(session_id, req.question_id)
    db.save_answer(session_id, req.question_id, req.answer, req.duration)
    if old_answer is not None and old_answer != req.answer:
        db.record_answer_change(session_id, req.question_id, old_answer, req.answer)

    answers = db.get_answers(session_id)
    completed = new_idx >= len(questions)
    if completed:
        db.mark_completed(session_id)

    return SubmitAnswerResponse(
        status="ok",
        answered_count=len(answers),
        total=len(questions),
        completed=completed,
        answer_history=[
            AnswerHistoryEntry(**h) for h in db.get_answer_history(session_id)
        ],
    )


@app.get("/api/test/session/{session_id}/answers", response_model=AnswersResponse)
def get_answers(session_id: str):
    """返回当前答案与修改历史（答题修改规则见 docs/API.md）。"""
    _session_or_404(session_id)
    return AnswersResponse(
        session_id=session_id,
        answers=db.get_answers(session_id),
        answer_history=[
            AnswerHistoryEntry(**h) for h in db.get_answer_history(session_id)
        ],
    )


@app.get("/api/test/session/{session_id}/result", response_model=ResultResponse)
def get_result(session_id: str):
    row = _session_or_404(session_id)
    questions = _session_questions(row)
    answers = db.get_answers(session_id)

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

    db.save_results(
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
