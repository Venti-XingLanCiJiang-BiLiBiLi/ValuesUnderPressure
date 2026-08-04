"""
题库版本路径解析（共享模块）。

被 question_bank 与 dimensions 共同引用，避免两者互相 import 造成循环依赖。
路径规则：<repo>/question-bank/<QUESTION_BANK_VERSION>。
"""

from __future__ import annotations

import os

# 版本由环境变量 QUESTION_BANK_VERSION 控制，默认 v1（docker-compose / Dockerfile 中可覆盖）。
DEFAULT_BANK_VERSION = os.environ.get("QUESTION_BANK_VERSION", "").strip() or "v1"


def resolve_bank_dir() -> str:
    """返回题库版本目录：<repo>/question-bank/<QUESTION_BANK_VERSION>。"""
    version = os.environ.get("QUESTION_BANK_VERSION", "").strip() or DEFAULT_BANK_VERSION
    return os.path.join(
        os.path.dirname(__file__), "..", "..", "question-bank", version
    )
