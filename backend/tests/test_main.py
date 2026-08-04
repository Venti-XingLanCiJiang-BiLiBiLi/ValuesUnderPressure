"""main.py 单元测试：result 接口必须要求全部题目完成。

覆盖修复点：
  - 未作答/部分作答时 GET result 返回 HTTP 409；
  - 全部作答后才允许生成结果；
  - result 返回维度级 confidence；
  - 修改已提交答案会记录 answer_history 且不改变进度。
"""
import pytest
from fastapi import HTTPException

from app import db
from app.main import get_answers, get_result, submit_answer
from app.question_bank import load_bucket_bank
from app.schemas import SubmitAnswerRequest
from app.selection import build_test


def _create_session(seed: int, answered_count: int):
    bank = load_bucket_bank()
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
    for d in res.dimensions.values():
        assert 0.0 <= d.score <= 100.0
        assert 0.0 <= d.confidence <= 1.0


def test_result_409_for_unknown_session():
    with pytest.raises(HTTPException) as exc:
        get_result("no_such_session")
    assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# 答题修改规则：允许修改已提交答案，记录 answer_history，不改变进度
# ---------------------------------------------------------------------------


def test_answer_modification_records_history():
    sid, questions = _create_session(seed=4, answered_count=0)
    q0 = questions[0]

    # 第一次作答
    submit_answer(sid, SubmitAnswerRequest(question_id=q0.id, answer="Y"))
    assert db.get_answer(sid, q0.id) == "Y"

    # 修改答案：应记录历史
    resp = submit_answer(sid, SubmitAnswerRequest(question_id=q0.id, answer="N"))
    assert db.get_answer(sid, q0.id) == "N"
    history = db.get_answer_history(sid)
    assert len(history) == 1
    assert history[0]["question_id"] == q0.id
    assert history[0]["old_answer"] == "Y"
    assert history[0]["new_answer"] == "N"
    assert resp.answer_history[0].old_answer == "Y"
    assert resp.answer_history[0].new_answer == "N"

    # 重复提交相同答案：不新增历史
    submit_answer(sid, SubmitAnswerRequest(question_id=q0.id, answer="N"))
    assert len(db.get_answer_history(sid)) == 1


def test_answer_modification_does_not_change_progress():
    sid, questions = _create_session(seed=6, answered_count=0)
    q0, q1 = questions[0], questions[1]

    submit_answer(sid, SubmitAnswerRequest(question_id=q0.id, answer="Y"))
    # 修改已提交的 q0 答案：指针不应前进（下一次取的仍是 q1）
    submit_answer(sid, SubmitAnswerRequest(question_id=q0.id, answer="N"))
    row = db.get_session(sid)
    assert row["current_index"] == 1
    assert questions[row["current_index"]].id == q1.id


def test_answers_endpoint_returns_current_and_history():
    sid, questions = _create_session(seed=5, answered_count=0)
    q0, q1 = questions[0], questions[1]

    submit_answer(sid, SubmitAnswerRequest(question_id=q0.id, answer="Y"))
    submit_answer(sid, SubmitAnswerRequest(question_id=q0.id, answer="N"))
    submit_answer(sid, SubmitAnswerRequest(question_id=q1.id, answer="Y"))

    res = get_answers(sid)
    assert res.session_id == sid
    assert res.answers[q0.id] == "N"
    assert res.answers[q1.id] == "Y"
    assert len(res.answer_history) == 1
    assert res.answer_history[0].question_id == q0.id
