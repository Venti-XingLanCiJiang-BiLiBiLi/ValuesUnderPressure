#!/usr/bin/env python3
"""
校验 question-bank/questions.json 是否满足 docs/DataValidation.md 中的规则。

用法:
    python scripts/validate_bank.py [path/to/questions.json]

退出码:
    0 -> 全部题目通过校验
    1 -> 存在被剔除的题目（详见标准输出）
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.question_bank import load_question_bank  # noqa: E402


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else None
    bank = load_question_bank(path)
    print(f"题库来源: {bank.source}")
    print(f"通过校验: {len(bank.questions)} 题")
    print(f"未通过校验并被剔除: {len(bank.invalid)} 条")
    for err in bank.invalid:
        print("  -", err)
    return 1 if bank.invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
