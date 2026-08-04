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
    confidence REAL
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
    """对已存在的旧库做增量迁移：为 results 表补 confidence 列。

    CREATE TABLE IF NOT EXISTS 不会给已存在的表加列，因此旧数据库需要 ALTER；
    用表存在性 + 列存在性双重判断，避免在极旧的库（尚无 results 表）上误执行 ALTER。
    """
    if await _table_exists(conn, "results") and not await _column_exists(
        conn, "results", "confidence"
    ):
        await conn.execute("ALTER TABLE results ADD COLUMN confidence REAL")


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
    question_version: str, length: int, dimensions: list[str], question_ids: list[str]
) -> str:
    session_id = uuid.uuid4().hex
    async with get_conn() as conn:
        await conn.execute(
            """INSERT INTO test_sessions
               (id, created_at, question_version, length, dimensions_json,
                question_ids_json, current_index, status)
               VALUES (?, ?, ?, ?, ?, ?, 0, 'in_progress')""",
            (
                session_id,
                datetime.datetime.now(_UTC).isoformat(),
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
    async with get_conn() as conn:
        await conn.execute(
            "UPDATE test_sessions SET status = 'completed' WHERE id = ?", (session_id,)
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
