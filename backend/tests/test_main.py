"""main.py 单元测试：result 接口必须要求全部题目完成。

覆盖修复点：
  - 未作答/部分作答时 GET result 返回 HTTP 409；
  - 全部作答后才允许生成结果。
"""
import pytest
from fastapi import HTTPException

from app import db
from app.main import get_result
from app.question_bank import load_question_bank
from app.selection import build_test


def _create_session(seed: int, answered_count: int):
    bank = load_question_bank()
    questions = build_test(bank, length=10, seed=seed)
    sid = db.create_session(
        bank.version(), len(questions), [], [q.id for q in questions]
    )
    for q in questions[:answered_count]:
        db.save_answer(sid, q.id, "Y", 3)
    return sid, questions


def test_result_409_when_no_answers():
    sid, _ = _create_session(seed=1, answered_count=0)
    with pytest.raises(HTTPException) as exc:
        get_result(sid)
    assert exc.value.status_code == 409


def test_result_409_when_partially_answered():
    sid, questions = _create_session(seed=2, answered_count=5)
    with pytest.raises(HTTPException) as exc:
        get_result(sid)
    assert exc.value.status_code == 409
    assert str(len(questions)) in str(exc.value.detail)  # 提示已作答/总数


def test_result_ok_when_all_answered():
    sid, questions = _create_session(seed=3, answered_count=10)
    res = get_result(sid)
    assert res.completed is True
    assert res.answered_count == len(questions)
    assert res.total == len(questions)
    assert res.dimensions
    for dim, d in res.dimensions.items():
        assert 0.0 <= d.score <= 100.0


def test_result_409_for_unknown_session():
    with pytest.raises(HTTPException) as exc:
        get_result("no_such_session")
    assert exc.value.status_code == 404
