"""
SQLite 持久化层（异步，基于 aiosqlite）。

表结构参考 docs/DatabaseSchema.md，并做了落地调整：
  - test_sessions 增加 length / dimensions_json / question_ids_json / status 字段，
    用于保存本次试卷的抽题结果，保证"获取下一题"接口在多次请求间保持一致；
  - answers 增加 answered_at；
  - results 表按维度落一行（含维度级 confidence），同时保存整体 confidence 到 sessions 表；
  - answer_history 表记录答案修改历史（题目、旧答案、新答案、修改时间）。

异步化说明（#8）：所有函数均为 async，沿用"每函数一次连接"的短连接模式，
避免跨请求共享连接；由事件循环串行调度，规避 SQLite 并发写锁竞争。

过期与清理（#10）：
  - test_sessions.expires_at 记录过期时间；create_session 默认 now + SESSION_TTL_DAYS 天，
    完成时 mark_completed 延长到 now + COMPLETED_SESSION_TTL_DAYS 天（已完成结果长期保留）；
  - cleanup_expired_sessions() 删除过期 session 及其关联数据（answers/results/answer_history），
    供后台定期清理任务调用（见 main.py _periodic_cleanup）。
"""

from __future__ import annotations

import datetime
import json
import os
import sqlite3
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import aiosqlite

_UTC = datetime.UTC

# 过期策略（可环境变量覆盖）：
#   SESSION_TTL_DAYS           进行中/默认 session 过期天数（默认 3）
#   COMPLETED_SESSION_TTL_DAYS 已完成 session 的延长保留天数（默认 15）
SESSION_TTL_DAYS = int(os.environ.get("SESSION_TTL_DAYS", "3"))
COMPLETED_SESSION_TTL_DAYS = int(os.environ.get("COMPLETED_SESSION_TTL_DAYS", "15"))

DB_PATH = os.environ.get(
    "APERSONALITYTEST_DB_PATH",
    os.path.join(os.path.dirname(__file__), "data", "app.db"),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS test_sessions (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    question_version TEXT NOT NULL,
    length INTEGER NOT NULL,
    dimensions_json TEXT NOT NULL,
    question_ids_json TEXT NOT NULL,
    current_index INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'in_progress',
    confidence REAL,
    expires_at TEXT
);

CREATE TABLE IF NOT EXISTS answers (
    session_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    answer TEXT NOT NULL,
    duration INTEGER,
    answered_at TEXT NOT NULL,
    PRIMARY KEY (session_id, question_id),
    FOREIGN KEY (session_id) REFERENCES test_sessions(id)
);

CREATE TABLE IF NOT EXISTS results (
    session_id TEXT NOT NULL,
    dimension TEXT NOT NULL,
    score REAL NOT NULL,
    consistency REAL,
    confidence REAL,
    PRIMARY KEY (session_id, dimension),
    FOREIGN KEY (session_id) REFERENCES test_sessions(id)
);

CREATE TABLE IF NOT EXISTS answer_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    question_id TEXT NOT NULL,
    old_answer TEXT NOT NULL,
    new_answer TEXT NOT NULL,
    changed_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES test_sessions(id)
);
"""


async def init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    async with get_conn() as conn:
        await conn.executescript(SCHEMA)
        await _migrate(conn)


async def _column_exists(conn: aiosqlite.Connection, table: str, column: str) -> bool:
    cur = await conn.execute(f"PRAGMA table_info({table})")
    rows = await cur.fetchall()
    return any(r["name"] == column for r in rows)


async def _table_exists(conn: aiosqlite.Connection, table: str) -> bool:
    cur = await conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name = ?", (table,)
    )
    rows = await cur.fetchall()
    return bool(rows)


async def _migrate(conn: aiosqlite.Connection) -> None:
    """对已存在的旧库做增量迁移。

    CREATE TABLE IF NOT EXISTS 不会给已存在的表加列，因此旧数据库需要 ALTER；
    用表存在性 + 列存在性双重判断，避免在极旧的库（尚无对应表）上误执行 ALTER。
    """
    # 已有迁移：results 补 confidence 列（#16 维度级置信度）
    if await _table_exists(conn, "results") and not await _column_exists(
        conn, "results", "confidence"
    ):
        await conn.execute("ALTER TABLE results ADD COLUMN confidence REAL")

    # #10：test_sessions 补 expires_at 列（Session 过期与数据清理）
    if await _table_exists(conn, "test_sessions") and not await _column_exists(
        conn, "test_sessions", "expires_at"
    ):
        await conn.execute("ALTER TABLE test_sessions ADD COLUMN expires_at TEXT")
        # 历史行回填：NULL expires_at 按 created_at + SESSION_TTL_DAYS 计算
        cur = await conn.execute(
            "SELECT id, created_at FROM test_sessions WHERE expires_at IS NULL"
        )
        rows = await cur.fetchall()
        now = datetime.datetime.now(_UTC)
        for r in rows:
            try:
                created = datetime.datetime.fromisoformat(r["created_at"])
            except ValueError:
                created = now
            exp = created + datetime.timedelta(days=SESSION_TTL_DAYS)
            await conn.execute(
                "UPDATE test_sessions SET expires_at = ? WHERE id = ?",
                (exp.isoformat(), r["id"]),
            )

    # 索引（IF NOT EXISTS 幂等，新旧库皆安全）
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sessions_expires ON test_sessions(expires_at)"
    )
    await conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_sessions_status ON test_sessions(status)"
    )


@asynccontextmanager
async def get_conn() -> AsyncIterator[aiosqlite.Connection]:
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        await conn.commit()
    finally:
        await conn.close()


async def create_session(
    question_version: str,
    length: int,
    dimensions: list[str],
    question_ids: list[str],
    expires_at: str | None = None,
) -> str:
    """创建测试会话。默认 expires_at = now + SESSION_TTL_DAYS 天（可传入覆盖）。"""
    session_id = uuid.uuid4().hex
    if expires_at is None:
        expires_at = (
            datetime.datetime.now(_UTC) + datetime.timedelta(days=SESSION_TTL_DAYS)
        ).isoformat()
    async with get_conn() as conn:
        await conn.execute(
            """INSERT INTO test_sessions
               (id, created_at, expires_at, question_version, length, dimensions_json,
                question_ids_json, current_index, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 0, 'in_progress')""",
            (
                session_id,
                datetime.datetime.now(_UTC).isoformat(),
                expires_at,
                question_version,
                length,
                json.dumps(dimensions, ensure_ascii=False),
                json.dumps(question_ids, ensure_ascii=False),
            ),
        )
    return session_id


async def get_session(session_id: str) -> sqlite3.Row | None:
    async with get_conn() as conn:
        cur = await conn.execute("SELECT * FROM test_sessions WHERE id = ?", (session_id,))
        return await cur.fetchone()


async def advance_pointer(session_id: str, new_index: int) -> None:
    async with get_conn() as conn:
        await conn.execute(
            "UPDATE test_sessions SET current_index = ? WHERE id = ?",
            (new_index, session_id),
        )


async def mark_completed(session_id: str) -> None:
    """标记完成并延长过期时间（已完成结果长期保留，默认 +COMPLETED_SESSION_TTL_DAYS 天）。"""
    async with get_conn() as conn:
        await conn.execute(
            """UPDATE test_sessions
               SET status = 'completed',
                   expires_at = ?
               WHERE id = ?""",
            (
                (
                    datetime.datetime.now(_UTC)
                    + datetime.timedelta(days=COMPLETED_SESSION_TTL_DAYS)
                ).isoformat(),
                session_id,
            ),
        )


async def save_answer(session_id: str, question_id: str, answer: str, duration: int | None) -> None:
    async with get_conn() as conn:
        await conn.execute(
            """INSERT INTO answers (session_id, question_id, answer, duration, answered_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(session_id, question_id) DO UPDATE SET
                 answer=excluded.answer, duration=excluded.duration,
                 answered_at=excluded.answered_at""",
            (session_id, question_id, answer, duration, datetime.datetime.now(_UTC).isoformat()),
        )


async def get_answers(session_id: str) -> dict:
    async with get_conn() as conn:
        cur = await conn.execute(
            "SELECT question_id, answer FROM answers WHERE session_id = ?", (session_id,)
        )
        rows = await cur.fetchall()
        return {row["question_id"]: row["answer"] for row in rows}


async def get_answer(session_id: str, question_id: str) -> str | None:
    """返回某题当前答案；尚未作答返回 None。"""
    async with get_conn() as conn:
        cur = await conn.execute(
            "SELECT answer FROM answers WHERE session_id = ? AND question_id = ?",
            (session_id, question_id),
        )
        row = await cur.fetchone()
        return row["answer"] if row else None


async def record_answer_change(
    session_id: str, question_id: str, old_answer: str, new_answer: str
) -> None:
    """记录一次答案修改（old -> new）。"""
    async with get_conn() as conn:
        await conn.execute(
            """INSERT INTO answer_history
               (session_id, question_id, old_answer, new_answer, changed_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                session_id,
                question_id,
                old_answer,
                new_answer,
                datetime.datetime.now().isoformat(timespec="seconds"),
            ),
        )


async def get_answer_history(session_id: str) -> list[dict]:
    """按时间顺序返回该会话的答案修改历史。"""
    async with get_conn() as conn:
        cur = await conn.execute(
            """SELECT question_id, old_answer, new_answer, changed_at
               FROM answer_history WHERE session_id = ? ORDER BY id ASC""",
            (session_id,),
        )
        rows = await cur.fetchall()
        return [dict(row) for row in rows]


async def cleanup_expired_sessions(cutoff: str | None = None) -> int:
    """删除所有已过期的 session 及其关联数据，返回删除的 session 数。

    expires_at 为 UTC ISO-8601 文本，同格式下字符串比较等价于时间比较；
    表外键未启用 ON DELETE CASCADE，故需按 session_id 逐表删除关联数据。
    """
    if cutoff is None:
        cutoff = datetime.datetime.now(_UTC).isoformat()
    async with get_conn() as conn:
        cur = await conn.execute(
            "SELECT id FROM test_sessions WHERE expires_at < ?", (cutoff,)
        )
        rows = await cur.fetchall()
        session_ids = [r["id"] for r in rows]
        for sid in session_ids:
            await conn.execute(
                "DELETE FROM answer_history WHERE session_id = ?", (sid,)
            )
            await conn.execute("DELETE FROM answers WHERE session_id = ?", (sid,))
            await conn.execute("DELETE FROM results WHERE session_id = ?", (sid,))
            await conn.execute("DELETE FROM test_sessions WHERE id = ?", (sid,))
    return len(session_ids)


async def save_results(session_id: str, dimension_scores: dict, confidence: float) -> None:
    async with get_conn() as conn:
        await conn.execute(
            "UPDATE test_sessions SET confidence = ? WHERE id = ?", (confidence, session_id)
        )
        for dim, r in dimension_scores.items():
            await conn.execute(
                """INSERT INTO results (session_id, dimension, score, consistency, confidence)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(session_id, dimension) DO UPDATE SET
                     score=excluded.score, consistency=excluded.consistency,
                     confidence=excluded.confidence""",
                (session_id, dim, r["score"], r["consistency"], r.get("confidence")),
            )
