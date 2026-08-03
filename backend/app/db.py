"""
SQLite 持久化层。

表结构参考 docs/DatabaseSchema.md，并做了落地调整：
  - test_sessions 增加 length / dimensions_json / question_ids_json / status 字段，
    用于保存本次试卷的抽题结果，保证"获取下一题"接口在多次请求间保持一致；
  - answers 增加 answered_at；
  - results 表按维度落一行，同时保存整体 confidence 到 sessions 表。
"""

from __future__ import annotations

import datetime
import json
import os
import sqlite3
import uuid
from contextlib import contextmanager
from typing import Iterator, List, Optional

_UTC = datetime.timezone.utc

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
    PRIMARY KEY (session_id, dimension),
    FOREIGN KEY (session_id) REFERENCES test_sessions(id)
);
"""


def init_db() -> None:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_conn() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def create_session(
    question_version: str, length: int, dimensions: List[str], question_ids: List[str]
) -> str:
    session_id = uuid.uuid4().hex
    with get_conn() as conn:
        conn.execute(
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


def get_session(session_id: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM test_sessions WHERE id = ?", (session_id,))
        return cur.fetchone()


def advance_pointer(session_id: str, new_index: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE test_sessions SET current_index = ? WHERE id = ?",
            (new_index, session_id),
        )


def mark_completed(session_id: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE test_sessions SET status = 'completed' WHERE id = ?", (session_id,)
        )


def save_answer(session_id: str, question_id: str, answer: str, duration: Optional[int]) -> None:
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO answers (session_id, question_id, answer, duration, answered_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(session_id, question_id) DO UPDATE SET
                 answer=excluded.answer, duration=excluded.duration,
                 answered_at=excluded.answered_at""",
            (session_id, question_id, answer, duration, datetime.datetime.now(_UTC).isoformat()),
        )


def get_answers(session_id: str) -> dict:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT question_id, answer FROM answers WHERE session_id = ?", (session_id,)
        )
        return {row["question_id"]: row["answer"] for row in cur.fetchall()}


def save_results(session_id: str, dimension_scores: dict, confidence: float) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE test_sessions SET confidence = ? WHERE id = ?", (confidence, session_id)
        )
        for dim, r in dimension_scores.items():
            conn.execute(
                """INSERT INTO results (session_id, dimension, score, consistency)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(session_id, dimension) DO UPDATE SET
                     score=excluded.score, consistency=excluded.consistency""",
                (session_id, dim, r["score"], r["consistency"]),
            )
