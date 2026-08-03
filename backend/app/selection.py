"""
分层随机组卷算法（按场景分类 + 按难度分层采样）。

规则（默认 50 题）:
  - must:        题库中 must 题按顺序每 4 题一桶（如 Q00441-444、Q00445-448…），
                 每桶随机抽 1 题得到候选（共 10 题），再从候选中随机取 5 题；
  - experimental: 随机抽 1 题；
  - 其余 10 个常规分类: 每个随机抽 4~5 题（默认合计 44 题，随机挑 4 个分类各抽
                 5 题、其余 6 个分类各抽 4 题），并在每个分类内按难度
                 （easy / medium / hard）比例分层采样。

来源: docs/QuestionSelection.md ("禁止从全部题目随机抽 N 题"),
      question-bank/question_bank_readme.md（must 锚定 / experimental 分类定义）
"""

from __future__ import annotations

import random
from collections import Counter
from typing import List, Optional

from .dimensions import DIMENSION_IDS
from .question_bank import QuestionBank, Question

MIN_LENGTH = 10
MAX_LENGTH = 120
DEFAULT_LENGTH = 50

# must: 每 4 题一桶（按题库顺序），每桶抽 1 题得到候选，再从候选随机取 MUST_TARGET 题
MUST_BUCKET_SIZE = 4
MUST_TARGET = 5
# experimental: 每张试卷固定抽 1 题
EXPERIMENTAL_TARGET = 1

# 难度分层顺序（按从易到难），用于常规分类内的分层采样
DIFFICULTY_ORDER = ["easy", "medium", "hard"]

# 除 must / experimental 之外的 10 个常规场景分类
REGULAR_CATEGORIES = [
    "personal_boundary",
    "privacy",
    "freedom",
    "safety",
    "wealth",
    "morality",
    "social",
    "future",
    "risk",
    "control",
]


def _must_buckets(bank: QuestionBank) -> List[List[Question]]:
    """把 must 题按题库顺序每 MUST_BUCKET_SIZE 题切成若干桶。"""
    must_pool = bank.by_category("must")
    return [
        must_pool[i : i + MUST_BUCKET_SIZE]
        for i in range(0, len(must_pool), MUST_BUCKET_SIZE)
    ]


def _must_candidates(bank: QuestionBank, rng: random.Random) -> List[Question]:
    """每桶随机抽 1 题，返回候选列表（默认 10 题）。"""
    candidates = []
    for bucket in _must_buckets(bank):
        if bucket:
            candidates.append(rng.choice(bucket))
    return candidates


def _pick_must(bank: QuestionBank, rng: random.Random) -> List[Question]:
    """must 抽题: 桶内各抽 1 题得到候选后，再随机取 MUST_TARGET 题。"""
    candidates = _must_candidates(bank, rng)
    return rng.sample(candidates, min(MUST_TARGET, len(candidates)))


def _split_quota_by_difficulty(
    available: dict, quota: int
) -> dict:
    """按各难度可用题数的比例把 quota 拆成每难度配额（最大余数法）。

    - 比例为该难度在分类内可用题数占比，稀缺难度不会被过度采样；
    - 无可用题的难度分到 0；
    - 返回的配额总和恒等于 quota。
    """
    total = sum(available.values())
    if total <= 0 or quota <= 0:
        return {d: 0 for d in DIFFICULTY_ORDER}

    alloc = {d: available.get(d, 0) * quota // total for d in DIFFICULTY_ORDER}
    assigned = sum(alloc.values())
    remainder = quota - assigned
    if remainder > 0:
        # 小数部分最大的难度优先拿余数，避免向 0 可用题的难度分配
        def _frac(d: str) -> float:
            return available.get(d, 0) * quota / total - alloc[d]

        for d in sorted(DIFFICULTY_ORDER, key=_frac, reverse=True)[:remainder]:
            alloc[d] += 1
    return alloc


def build_test(
    bank: QuestionBank,
    length: int = DEFAULT_LENGTH,
    dimensions: Optional[List[str]] = None,
    seed: Optional[int] = None,
) -> List[Question]:
    """按场景分类生成一份随机试卷。

    - must: 固定按每 4 题一桶抽 1 题 → 候选，再随机取 MUST_TARGET(5) 题；
    - experimental: 固定随机抽 1 题；
    - 其余 10 个常规分类: 均分剩余名额（默认 50 题时每类 4~5 题，随机挑 4 个分类
      各抽 5 题、其余 6 个分类各抽 4 题），每个分类内再按难度
      easy/medium/hard 的比例分层采样；
    - 相同 seed 下结果可复现；

    如果指定 `dimensions`：
    - 从按分类抽出的候选题中只保留匹配指定维度的题目；
    - 缺口按相同优先级（常规 → must → experimental）回补，回补题同样限定维度。
    """
    rng = random.Random(seed)
    length = max(MIN_LENGTH, min(MAX_LENGTH, length))
    dim_set = set(dimensions) if dimensions else None

    # 辅助：判断题目是否匹配指定维度（未指定时全部通过）
    def _matches_dim(q: Question) -> bool:
        if dim_set is None:
            return True
        return any(d in dim_set for d in q.dimensions)

    selected: List[Question] = []
    selected_ids = set()

    # 1) must: 10 桶各抽 1 题 → 候选 10 题 → 随机取 5 题
    for q in _pick_must(bank, rng):
        selected.append(q)
        selected_ids.add(q.id)

    # 2) experimental: 随机抽 1 题
    exp_pool = bank.by_category("experimental")
    if exp_pool:
        q = rng.choice(exp_pool)
        selected.append(q)
        selected_ids.add(q.id)

    # 3) 其余 10 个常规分类: 均分剩余名额，余数随机分配给部分分类
    remaining = max(0, length - len(selected))
    if remaining > 0 and REGULAR_CATEGORIES:
        base = remaining // len(REGULAR_CATEGORIES)
        extra = remaining % len(REGULAR_CATEGORIES)
        quotas = {cat: base for cat in REGULAR_CATEGORIES}
        for cat in rng.sample(REGULAR_CATEGORIES, extra):
            quotas[cat] += 1

        for cat in REGULAR_CATEGORIES:
            cat_pool = [q for q in bank.by_category(cat) if q.id not in selected_ids]
            cat_quota = quotas[cat]
            if cat_quota <= 0 or not cat_pool:
                continue

            # 分层: 按各难度可用题数比例分配配额，再从各难度池内随机取
            available = Counter(q.difficulty for q in cat_pool)
            diff_quotas = _split_quota_by_difficulty(available, cat_quota)
            taken = 0
            for d in DIFFICULTY_ORDER:
                d_pool = [q for q in cat_pool if q.difficulty == d]
                rng.shuffle(d_pool)
                for q in d_pool[: diff_quotas[d]]:
                    selected.append(q)
                    selected_ids.add(q.id)
                    taken += 1

            # 某难度不足时，从该分类其余题目补齐，尽量满足分类配额
            if taken < cat_quota:
                leftover = [q for q in cat_pool if q.id not in selected_ids]
                rng.shuffle(leftover)
                for q in leftover[: cat_quota - taken]:
                    selected.append(q)
                    selected_ids.add(q.id)
                    taken += 1

    # 3.5) 维度筛选：如果指定了 dimensions，过滤已选题目
    if dim_set:
        selected = [q for q in selected if _matches_dim(q)]
        selected_ids = {q.id for q in selected}

    # 4) 回补缺口：按优先级分层补齐，同时遵守维度限制。
    #    优先级：常规分类 → must → experimental。
    shortfall = length - len(selected)
    if shortfall > 0:
        # 4a) 优先从常规分类中补
        regular_fallback = [
            q
            for q in bank.active_questions()
            if q.id not in selected_ids
            and q.category not in ("must", "experimental")
            and _matches_dim(q)
        ]
        rng.shuffle(regular_fallback)
        for q in regular_fallback[:shortfall]:
            selected.append(q)
            selected_ids.add(q.id)

    shortfall = length - len(selected)
    if shortfall > 0:
        # 4b) 不足再从 must 中补
        must_fallback = [
            q
            for q in bank.active_questions()
            if q.id not in selected_ids
            and q.category == "must"
            and _matches_dim(q)
        ]
        rng.shuffle(must_fallback)
        for q in must_fallback[:shortfall]:
            selected.append(q)
            selected_ids.add(q.id)

    shortfall = length - len(selected)
    if shortfall > 0:
        # 4c) 最后从 experimental 中补
        exp_fallback = [
            q
            for q in bank.active_questions()
            if q.id not in selected_ids
            and q.category == "experimental"
            and _matches_dim(q)
        ]
        rng.shuffle(exp_fallback)
        for q in exp_fallback[:shortfall]:
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
