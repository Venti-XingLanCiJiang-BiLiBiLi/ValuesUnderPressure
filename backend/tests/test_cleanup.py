"""#10 Session 过期与数据清理机制：db 层清理逻辑测试。

覆盖：
  - create_session 写入默认/自定义 expires_at；
  - mark_completed 延长过期时间（已完成结果长期保留）；
  - cleanup_expired_sessions 删除过期 session 及其关联数据（answers/results/answer_history）；
  - 未过期 session 不受影响。
"""
import datetime

from app import db

_UTC = datetime.UTC


async def test_create_session_sets_default_expires_at():
    sid = await db.create_session("v1", 10, [], ["q1", "q2"])
    row = await db.get_session(sid)
    assert row is not None
    assert row["expires_at"] is not None
    created = datetime.datetime.fromisoformat(row["created_at"])
    exp = datetime.datetime.fromisoformat(row["expires_at"])
    # 默认过期 = created_at + SESSION_TTL_DAYS 天（同一次调用内微秒级误差，用容差比较）
    expected = datetime.timedelta(days=db.SESSION_TTL_DAYS)
    assert abs((exp - created) - expected) < datetime.timedelta(seconds=5)


async def test_create_session_with_custom_expires_at():
    custom = (datetime.datetime.now(_UTC) - datetime.timedelta(hours=1)).isoformat()
    sid = await db.create_session("v1", 10, [], ["q1"], expires_at=custom)
    row = await db.get_session(sid)
    assert row["expires_at"] == custom


async def test_mark_completed_extends_expiry():
    sid = await db.create_session("v1", 10, [], ["q1"])
    before = (await db.get_session(sid))["expires_at"]
    await db.mark_completed(sid)
    after = (await db.get_session(sid))["expires_at"]
    before_dt = datetime.datetime.fromisoformat(before)
    after_dt = datetime.datetime.fromisoformat(after)
    assert after_dt > before_dt
    # 完成后的保留期 ≈ now + COMPLETED_SESSION_TTL_DAYS 天（容差比较）
    expected = datetime.timedelta(days=db.COMPLETED_SESSION_TTL_DAYS)
    assert (
        abs((after_dt - datetime.datetime.now(_UTC)) - expected)
        < datetime.timedelta(seconds=5)
    )


async def test_cleanup_removes_expired_and_related():
    expired_sid = await db.create_session(
        "v1",
        10,
        [],
        ["q1"],
        expires_at=(datetime.datetime.now(_UTC) - datetime.timedelta(hours=1)).isoformat(),
    )
    await db.save_answer(expired_sid, "q1", "Y", 1)
    await db.save_results(
        expired_sid,
        {"dim1": {"score": 50.0, "consistency": 1.0, "confidence": 0.9}},
        0.9,
    )
    await db.record_answer_change(expired_sid, "q1", "N", "Y")

    active_sid = await db.create_session("v1", 10, [], ["q1"])

    deleted = await db.cleanup_expired_sessions()
    assert deleted >= 1
    assert await db.get_session(expired_sid) is None
    assert await db.get_session(active_sid) is not None
    # 关联数据也应被清理
    assert await db.get_answers(expired_sid) == {}
    assert await db.get_answer_history(expired_sid) == []


async def test_cleanup_nothing_expired_returns_zero():
    await db.create_session("v1", 10, [], ["q1"])
    deleted = await db.cleanup_expired_sessions()
    assert deleted == 0
