#!/usr/bin/env python3
"""
不依赖 FastAPI/uvicorn 的核心流程冒烟测试：
  加载题库 -> 分层抽题 -> 模拟作答 -> 计分 -> 打印结果

用于在无法安装 web 框架依赖的环境中，验证 selection / scoring / db 模块的正确性。
"""
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app import db  # noqa: E402
from app.question_bank import load_question_bank  # noqa: E402
from app.scoring import score_session  # noqa: E402
from app.selection import build_test, coverage_report  # noqa: E402


def main():
    db.init_db()
    bank = load_question_bank()
    print(f"题库: {bank.source}, 有效题数: {len(bank.questions)}, 无效: {len(bank.invalid)}")

    questions = build_test(bank, length=30, seed=7)
    print(f"本次试卷题量: {len(questions)}")
    print("维度覆盖:", coverage_report(questions))

    session_id = db.create_session(
        bank.version(), len(questions), [], [q.id for q in questions]
    )
    print("session_id:", session_id)

    rnd = random.Random(7)
    for i, q in enumerate(questions):
        answer = rnd.choice(["Y", "N"])
        db.save_answer(session_id, q.id, answer, duration=rnd.randint(2, 15))
        db.advance_pointer(session_id, i + 1)
    db.mark_completed(session_id)

    answers = db.get_answers(session_id)
    result = score_session(questions, answers)

    print("\n=== 维度结果 ===")
    for dim, r in result.dimensions.items():
        print(f"{dim:18s} score={r.score:6.1f} consistency={r.consistency} "
              f"tendency={r.tendency} n={r.question_count}")

    print("\n整体置信度:", result.confidence)
    print("矛盾组合:", result.conflicts or "无")
    print("情境依赖(低一致性)维度:", result.uncertain_dimensions or "无")

    db.save_results(
        session_id,
        {d: {"score": r.score, "consistency": r.consistency} for d, r in result.dimensions.items()},
        result.confidence,
    )
    print("\n结果已写入数据库:", db.DB_PATH)


if __name__ == "__main__":
    main()
