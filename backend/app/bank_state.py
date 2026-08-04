"""共享题库实例状态（#15 路由拆分）。

多个路由模块（meta/admin/sessions）需要访问同一个 BucketBank 实例，
热更新（reload_bank）需要在运行期替换该实例。
集中管理在此模块，避免路由模块与入口模块之间循环导入。
"""
from __future__ import annotations

import threading

from .question_bank import BucketBank, load_bucket_bank

_bank: BucketBank | None = None
_bank_lock = threading.Lock()


def get_bank() -> BucketBank:
    global _bank
    if _bank is None:
        new_bank = load_bucket_bank()
        with _bank_lock:
            if _bank is None:
                _bank = new_bank
    return _bank


def set_bank(bank: BucketBank) -> None:
    """热更新时替换题库实例（持锁，避免并发读取到半初始化状态）。"""
    global _bank
    with _bank_lock:
        _bank = bank
