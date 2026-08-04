#!/usr/bin/env python3
"""
生成题库版本的 manifest.json（记录 questions.json / dimensions.json 的 sha256）。

用法:
    python scripts/generate_manifest.py [path/to/question-bank/v1]

不传参数时默认处理当前题库版本目录（resolve_bank_dir，由 QUESTION_BANK_VERSION
控制）。计算 questions.json 与 dimensions.json 的 sha256 后写入该目录下的
manifest.json，供 scripts/validate_bank.py 校验，确保两个文件属于同一题库版本。

退出码:
    0 -> 生成成功
    1 -> 缺少必要文件（questions.json / dimensions.json）
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.bank_paths import resolve_bank_dir
from app.manifest import MANIFEST_FILENAME, build_manifest


def _default_dir() -> str:
    """默认处理当前题库版本目录 question-bank/<QUESTION_BANK_VERSION>/。"""
    return resolve_bank_dir()


def main() -> int:
    bank_dir = sys.argv[1] if len(sys.argv) > 1 else _default_dir()
    manifest = build_manifest(bank_dir)
    out_path = os.path.join(bank_dir, MANIFEST_FILENAME)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"已生成 manifest: {out_path}")
    print(f"  bank_version      = {manifest['bank_version']}")
    print(f"  questions_file    = {manifest['questions_file']}")
    print(f"  questions_sha256  = {manifest['questions_sha256']}")
    print(f"  dimensions_file   = {manifest['dimensions_file']}")
    print(f"  dimensions_sha256 = {manifest['dimensions_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
