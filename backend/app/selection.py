"""
分层随机组卷算法。

来源: docs/QuestionSelection.md ("禁止从全部题目随机抽 N 题"),
      question-bank/question_bank_readme.md 中 must 分类的"锚定"定义。

流程:
  选择测试长度 -> 确定维度配额 -> 每个维度随机抽题 -> 检查重复和覆盖 -> 生成测试卷
"""

from __future__ import annotations

import random
from typing import List, Optional

from .dimensions import DIMENSION_IDS
from .question_bank import QuestionBank, Question

MIN_LENGTH = 10
MAX_LENGTH = 120
DEFAULT_LENGTH = 40
# 每张试卷固定出现的"必答题"（锚定题）数量，用于跨用户结果的可比较性
ANCHOR_COUNT = 4


def _anchor_questions(
    bank: QuestionBank, count: int, rng: random.Random
) -> List[Question]:
    """从 must 分类中随机抽取指定数量的锚定题。

    - 锚定题必须是 category == must 的题目；
    - 使用调用方传入的带 seed 的 rng，保证同 seed 下可复现；
    - 数量不足时返回全部 must 题。
    """
    must_pool = bank.by_category("must")
    if count <= 0 or not must_pool:
        return []
    if count >= len(must_pool):
        return list(must_pool)
    return rng.sample(must_pool, count)


def build_test(
    bank: QuestionBank,
    length: int = DEFAULT_LENGTH,
    dimensions: Optional[List[str]] = None,
    seed: Optional[int] = None,
) -> List[Question]:
    """按维度分层生成一份随机试卷。

    - 每份试卷从 must 分类中随机抽取一组"锚定题"（可复现，seed 相同则结果相同）；
    - 剩余名额在目标维度间尽量均分配额，逐维度随机抽题；
    - 一题可同时覆盖多个维度，因此实际维度覆盖数通常会超过名义配额；
    - 若某维度候选题不足，缺口自动回补给题量充足的维度。
    """
    rng = random.Random(seed)
    length = max(MIN_LENGTH, min(MAX_LENGTH, length))
    target_dims = dimensions or DIMENSION_IDS
    target_dims = [d for d in target_dims if d in DIMENSION_IDS] or DIMENSION_IDS

    selected: List[Question] = []
    selected_ids = set()

    anchors = _anchor_questions(
        bank, min(ANCHOR_COUNT, max(0, length // 8)), rng
    )
    for q in anchors:
        selected.append(q)
        selected_ids.add(q.id)

    remaining_budget = max(0, length - len(selected))
    if remaining_budget == 0 or not target_dims:
        rng.shuffle(selected)
        return selected

    base_quota = remaining_budget // len(target_dims)
    extra = remaining_budget % len(target_dims)
    quotas = {d: base_quota for d in target_dims}
    # 把不能整除的余数随机分配给部分维度，避免每次试卷长度都完全一样地"整除"
    for d in rng.sample(target_dims, extra):
        quotas[d] += 1

    shortfall = 0
    for dim in target_dims:
        pool = bank.by_dimension(dim, exclude_ids=selected_ids)
        rng.shuffle(pool)
        take = pool[: quotas[dim]]
        for q in take:
            if q.id not in selected_ids:
                selected.append(q)
                selected_ids.add(q.id)
        if len(take) < quotas[dim]:
            shortfall += quotas[dim] - len(take)

    # 用其余题目回补配额缺口，保证试卷总量尽量贴近目标长度
    if shortfall > 0:
        fallback_pool = [
            q for q in bank.active_questions() if q.id not in selected_ids
        ]
        rng.shuffle(fallback_pool)
        for q in fallback_pool[:shortfall]:
            selected.append(q)
            selected_ids.add(q.id)

    rng.shuffle(selected)
    return selected


def coverage_report(questions: List[Question]) -> dict:
    """返回本次试卷对各维度的覆盖题数，便于调试/单测。"""
    report = {d: 0 for d in DIMENSION_IDS}
    for q in questions:
        for d in q.dimensions:
            report[d] += 1
    return report
