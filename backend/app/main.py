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

import asyncio
import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
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
from .bank_state import get_bank
from .rate_limit import RateLimitExceeded, _rate_limit_exceeded_handler, limiter
from .routers import admin, meta, sessions

# 兼容旧导入：测试直接 `from app.main import ...`。
# 这些符号实际定义在路由模块，此处 re-export 以保持旧导入路径可用。
from .routers.admin import reload_bank  # noqa: F401  (re-export for tests)
from .routers.sessions import (  # noqa: F401  (re-export for tests)
    get_answers,
    get_result,
    submit_answer,
)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Initialize logging early so startup logs follow configured format.
    init_logging()

    await db.init_db()
    bank = get_bank()
    logger.info(
        "题库就绪: 版本=%s 索引组数=%d 总题数=%d",
        bank.version(),
        len(bank.groups()),
        bank.total_questions(),
    )
    # #10: 启动后台定期清理任务（Session 过期与数据清理），随应用关闭取消。
    cleanup_task = asyncio.create_task(_periodic_cleanup())
    try:
        yield
    finally:
        cleanup_task.cancel()


async def _periodic_cleanup() -> None:
    """后台定期清理过期 session（issue #10）。

    启动后立即执行一次，之后每 CLEANUP_INTERVAL_HOURS（默认 3）小时清理一次；
    单次异常不中断循环，记录日志后继续等待下一周期。
    """
    interval = float(os.environ.get("CLEANUP_INTERVAL_HOURS", "3")) * 3600
    while True:
        try:
            deleted = await db.cleanup_expired_sessions()
            if deleted > 0:
                logger.info("已清理 %d 条过期 session", deleted)
        except Exception:
            logger.exception("定期清理过期 session 失败")
        await asyncio.sleep(interval)


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

# API 限流与防滥用（#9）：挂载 slowapi limiter + 429 异常处理器
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 路由挂载：按域拆分到 app/routers/（#15）
# ---------------------------------------------------------------------------
app.include_router(meta.router)
app.include_router(admin.router)
app.include_router(sessions.router)






