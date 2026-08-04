#!/usr/bin/env python3
"""
校验 question-bank/questions.json 是否满足 docs/DataValidation.md 中的规则。

用法:
    python scripts/validate_bank.py [path/to/questions.json]

退出码:
    0 -> 全部题目通过校验
    1 -> 存在被剔除的题目（详见标准输出）

说明:
    全量校验直接复用 question_bank 模块的 _validate_raw / _to_question，
    不经过已弃用的 load_question_bank / QuestionBank（分桶索引懒加载
    BucketBank 不逐题校验，不适合作为校验入口）。
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.bank_paths import resolve_bank_dir
from app.question_bank import _to_question, _validate_raw


def _default_path() -> str:
    """默认校验当前版本题库的合并文件 question-bank/<version>/questions.json。"""
    return os.path.join(resolve_bank_dir(), "questions.json")


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else _default_path()
    with open(path, "r", encoding="utf-8") as f:
        raw_list = json.load(f)

    valid = 0
    invalid: list[str] = []
    seen_ids: set[str] = set()
    for raw in raw_list:
        errors = _validate_raw(raw, seen_ids)
        if errors:
            invalid.extend(errors)
            continue
        seen_ids.add(raw["id"])
        if _to_question(raw) is None:
            invalid.append(f"[{raw.get('id')}] 题目结构无法解析")
            continue
        valid += 1

    print(f"题库来源: {path}")
    print(f"通过校验: {valid} 题")
    print(f"未通过校验并被剔除: {len(invalid)} 条")
    for err in invalid:
        print("  -", err)
    return 1 if invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
