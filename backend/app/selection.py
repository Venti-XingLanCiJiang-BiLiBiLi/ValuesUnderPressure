"""
桶驱动随机组卷算法（依赖分桶索引，不加载全量题库）。

规则（默认 50 题）:
  - 组卷按分桶索引（questions.index.json）中的维度组抽题，不再依赖全量题库；
  - 每个组的抽题采用「先抽桶、再在桶内随机取题」：
      · 某组 m 桶、d 题，抽 n 题（d >= n）时，先抽 k = min(n, m) 桶（不放回随机）；
      · 候选不足 n 题时，重复抽桶（从剩余桶继续随机抽取）补充；
      · 从候选中随机取 n 题，不重复；
      · 组内总题数 d < n 时，按 fallback（从其它组补齐）处理；
  - must / experimental 作为特殊组参与抽题；
  - 整卷最后校验是否有重复题，若有则按 fallback 重抽该题；
  - 放弃按难度（easy / medium / hard）分层抽取。

来源: docs/QuestionSelection.md ("禁止从全部题目随机抽 N 题"),
      question-bank/question_bank_readme.md（must 锚定 / experimental 分类定义）
"""

from __future__ import annotations

import random
from typing import List, Optional

from .dimensions import DIMENSION_IDS
from .question_bank import BucketBank, Question

MIN_LENGTH = 10
MAX_LENGTH = 120
DEFAULT_LENGTH = 50

# must: 每张试卷固定抽 MUST_TARGET 题（锚定题）
MUST_TARGET = 5
# experimental: 每张试卷固定抽 1 题
EXPERIMENTAL_TARGET = 1

# 分桶索引中的特殊组名
MUST_GROUP = "must"
EXP_GROUP = "experimental"


def _draw_from_group(
    group: dict,
    n: int,
    rng: random.Random,
    bank: BucketBank,
    exclude_ids: set,
) -> List[Question]:
    """从某组（m 桶、d 题）抽 n 题（桶驱动）。

    规则（d >= n 时）：
      1. 先抽 k = min(n, m) 桶（不放回随机）；
      2. 收集这 k 桶全部题目作为候选；
      3. 候选不足 n 题时，重复抽桶（从剩余桶继续随机抽取）补充，直到候选 >= n
         或所有桶都被抽过；
      4. 从候选中随机取 n 题，不重复（排除 exclude_ids 与已取题目）。

    返回抽到的题目列表（可能少于 n —— 组内可用题不足时，由上层 fallback 补齐）。
    """
    files = list(group.get("files", []))
    m = len(files)
    if n <= 0 or not files:
        return []

    exclude_ids = set(exclude_ids)
    pool: List[Question] = []
    seen = set(exclude_ids)
    loaded_paths: set = set()

    def _absorb(f: dict) -> None:
        if f["path"] in loaded_paths:
            return
        loaded_paths.add(f["path"])
        for q in bank.load_bucket(f["path"]):
            if q.id not in seen:
                pool.append(q)
                seen.add(q.id)

    # 1) 先抽 k 桶
    k = min(n, m)
    for f in rng.sample(files, k):
        _absorb(f)

    # 2) 候选不足 n 题：重复抽桶（从剩余桶随机补充）
    rest = [f for f in files if f["path"] not in loaded_paths]
    rng.shuffle(rest)
    for f in rest:
        if len(pool) >= n:
            break
        _absorb(f)

    # 3) 从候选中随机取 n 题，不重复
    rng.shuffle(pool)
    return pool[:n]


def _dedupe_with_fallback(
    bank: BucketBank,
    selected: List[Question],
    rng: random.Random,
    dim_set: Optional[set],
) -> List[Question]:
    """去重校验：若出现重复题，该题按 fallback 从未选题目中重抽替换。"""
    seen: set = set()
    result: List[Question] = []

    extra_pool: List[Question] = []
    for g in bank.groups():
        for q in bank.questions_in_group(g["name"]):
            extra_pool.append(q)
    if dim_set is not None:
        extra_pool = [q for q in extra_pool if any(d in dim_set for d in q.dimensions)]
    rng.shuffle(extra_pool)
    ei = 0

    for q in selected:
        if q.id in seen:
            while ei < len(extra_pool) and extra_pool[ei].id in seen:
                ei += 1
            if ei < len(extra_pool):
                repl = extra_pool[ei]
                result.append(repl)
                seen.add(repl.id)
                ei += 1
            # 无可用替换时跳过该重复题，保持结果无重复
        else:
            result.append(q)
            seen.add(q.id)
    return result


def build_test(
    bank: BucketBank,
    length: int = DEFAULT_LENGTH,
    dimensions: Optional[List[str]] = None,
    seed: Optional[int] = None,
) -> List[Question]:
    """按分桶索引生成一份随机试卷（桶驱动，无难度分层）。

    - must: 固定抽 MUST_TARGET(5) 题（桶驱动）；
    - experimental: 固定抽 1 题；
    - 其余维度组: 均分剩余名额（默认 50 题时，随机挑 4 个维度各抽 5 题、
      其余 6 个维度各抽 4 题），每组内按「先抽桶、再抽题」的方式抽取；
    - 组内题数不足（d < n）时按 fallback 补齐（优先级：维度组 → must → experimental）；
    - 整卷最后校验重复题，若有则按 fallback 重抽；
    - 相同 seed 下结果可复现。

    如果指定 `dimensions`：只从这些维度组抽题，且题目须包含指定维度；
    缺口按相同优先级回补，回补题同样限定维度。
    """
    rng = random.Random(seed)
    length = max(MIN_LENGTH, min(MAX_LENGTH, length))
    dim_set = set(dimensions) if dimensions else None

    groups = bank.groups()
    dim_groups = [g for g in groups if g["type"] == "dimension"]
    must_group = bank.group(MUST_GROUP)
    exp_group = bank.group(EXP_GROUP)

    selected: List[Question] = []
    taken: set = set()

    # 辅助：判断题目是否匹配指定维度（未指定时全部通过）
    def _matches_dim(q: Question) -> bool:
        if dim_set is None:
            return True
        return any(d in dim_set for d in q.dimensions)

    def _take(qs: List[Question]) -> None:
        for q in qs:
            if q is not None and q.id not in taken:
                selected.append(q)
                taken.add(q.id)

    # 1) must（锚定题）
    if must_group:
        _take(_draw_from_group(must_group, MUST_TARGET, rng, bank, taken))

    # 2) experimental
    if exp_group:
        _take(_draw_from_group(exp_group, EXPERIMENTAL_TARGET, rng, bank, taken))

    # 3) 常规维度组：均分剩余名额，余数随机分配给部分维度
    remaining = max(0, length - len(selected))
    pool_groups = [g for g in dim_groups if dim_set is None or g["name"] in dim_set]
    if not pool_groups:
        pool_groups = list(dim_groups)  # 指定维度不存在时回退到全部维度
    if remaining > 0 and pool_groups:
        base = remaining // len(pool_groups)
        extra = remaining % len(pool_groups)
        quotas = {g["name"]: base for g in pool_groups}
        for g in rng.sample(pool_groups, extra):
            quotas[g["name"]] += 1
        for g in pool_groups:
            n = quotas[g["name"]]
            if n <= 0:
                continue
            _take(_draw_from_group(g, n, rng, bank, taken))

    # 3.5) 维度筛选：指定 dimensions 时只保留匹配题
    if dim_set:
        selected = [q for q in selected if _matches_dim(q)]
        taken = {q.id for q in selected}

    # 4) 回补缺口（优先级：维度组 → must → experimental）
    shortfall = length - len(selected)
    if shortfall > 0:
        fb: List[Question] = []
        for g in pool_groups:
            for q in bank.questions_in_group(g["name"]):
                if q.id not in taken and _matches_dim(q):
                    fb.append(q)
        rng.shuffle(fb)
        _take(fb[:shortfall])

    shortfall = length - len(selected)
    if shortfall > 0 and must_group:
        fb = [q for q in bank.questions_in_group(MUST_GROUP)
              if q.id not in taken and _matches_dim(q)]
        rng.shuffle(fb)
        _take(fb[:shortfall])

    shortfall = length - len(selected)
    if shortfall > 0 and exp_group:
        fb = [q for q in bank.questions_in_group(EXP_GROUP)
              if q.id not in taken and _matches_dim(q)]
        rng.shuffle(fb)
        _take(fb[:shortfall])

    # 5) 去重校验 + fallback 重抽
    selected = _dedupe_with_fallback(bank, selected, rng, dim_set)

    rng.shuffle(selected)
    return selected


def coverage_report(questions: List[Question]) -> dict:
    """返回本次试卷对各维度的覆盖题数，便于调试/单测。"""
    report = {d: 0 for d in DIMENSION_IDS}
    for q in questions:
        for d in q.dimensions:
            report[d] += 1
    return report
