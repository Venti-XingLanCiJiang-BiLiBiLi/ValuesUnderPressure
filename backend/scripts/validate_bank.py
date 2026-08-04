#!/usr/bin/env python3
"""
校验题库版本是否满足 docs/DataValidation.md 中的规则，并优先校验 manifest。

用法:
    python scripts/validate_bank.py [path/to/question-bank/v1]
    # 不传参数：默认校验当前题库版本目录（QUESTION_BANK_VERSION 控制）
    # 传目录：校验该版本目录的 manifest（文件存在 / schema_version / 文件名引用 /
    #         questions.json 与 dimensions.json sha256）后再全量校验题目
    # 传单个 questions.json 文件：旧行为，只全量校验该文件（跳过 manifest）

退出码:
    0 -> manifest 校验通过且全部题目通过校验
    1 -> manifest 缺失/校验失败，或存在被剔除的题目（详见标准输出）

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
from app.manifest import MANIFEST_FILENAME, ManifestError, validate_manifest
from app.question_bank import _to_question, _validate_raw


def _default_dir() -> str:
    """默认校验当前版本题库目录 question-bank/<version>/。"""
    return resolve_bank_dir()


def _validate_questions_file(path: str) -> int:
    """全量校验单个 questions.json 文件（旧行为）。"""
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


def _validate_version_dir(bank_dir: str) -> int:
    """默认入口：先校验 manifest，再全量校验 manifest 引用的 questions.json。"""
    manifest_path = os.path.join(bank_dir, MANIFEST_FILENAME)
    if not os.path.isfile(manifest_path):
        print(f"错误: 未找到 manifest: {manifest_path}")
        print("修复建议: 运行 python scripts/generate_manifest.py 生成 manifest.json")
        return 1
    try:
        manifest = validate_manifest(bank_dir)
    except ManifestError as e:
        print(f"manifest 校验失败: {e}")
        return 1
    print(f"manifest 校验通过: {manifest_path}")
    print(f"  题库版本: {manifest['bank_version']}")
    return _validate_questions_file(os.path.join(bank_dir, manifest["questions_file"]))


def main() -> int:
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    if arg and os.path.isfile(arg):
        # 传单个文件：旧行为，只全量校验该文件
        return _validate_questions_file(arg)
    bank_dir = arg or _default_dir()
    return _validate_version_dir(bank_dir)


if __name__ == "__main__":
    raise SystemExit(main())
