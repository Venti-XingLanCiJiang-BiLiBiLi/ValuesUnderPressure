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


def is_production() -> bool:
    """生产/开发判定：环境变量 APP_ENV=production|prod 视为生产环境。

    统一放在共享模块 bank_paths（question_bank 与 dimensions 共用，避免循环依赖），
    全项目只有一个 production 判定来源，不新增重复配置。
    """
    return os.environ.get("APP_ENV", "").strip().lower() in ("production", "prod")
