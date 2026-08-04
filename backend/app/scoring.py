"""
评分算法实现。

来源:
  docs/ScoringAlgorithm.md  -> 累加 + 归一化(0-100) + 一致性分析
  docs/ResultInterpretation.md -> 倾向方向 / 典型行为描述 / 矛盾分析 / 不确定性
"""

from __future__ import annotations

from dataclasses import dataclass

from .dimensions import CONFLICT_PAIRS, DIMENSIONS
from .question_bank import Question

CONSISTENCY_LOW_THRESHOLD = 0.5
# 倾向分类阈值与前端 bar 颜色阈值（frontend/src/config/theme.ts SCORE_THRESHOLDS）对齐：
# >= 60 高分倾向 / <= 40 低分倾向 / 40~60 中间地带
HIGH_SCORE_THRESHOLD = 60
LOW_SCORE_THRESHOLD = 40
# 维度级置信度：低于该题量时 confidence 会按数量因子衰减（样本量不足 -> 低可信）
MIN_QUESTION_THRESHOLD = 5


@dataclass
class DimensionResult:
    dimension: str
    name: str
    raw_score: int
    min_possible: int
    max_possible: int
    score: float  # 0-100 归一化分数
    consistency: float | None  # 0-1，None 表示样本不足
    tendency: str  # 描述方向的文字
    description: str
    question_count: int
    confidence: float  # 0-1，维度级可信度（综合题量 / 一致性 / 权重覆盖）


@dataclass
class TestResult:
    dimensions: dict[str, DimensionResult]
    confidence: float
    conflicts: list[dict]
    uncertain_dimensions: list[str]


def _contribution(weight_yes: int, weight_no: int, answer: str) -> int:
    return weight_yes if answer == "Y" else weight_no


def score_session(
    questions: list[Question], answers: dict[str, str]
) -> TestResult:
    """根据已作答的题目计算各维度得分、一致性与矛盾分析。

    answers: {question_id: "Y" | "N"}，只统计已回答的题目。
    """
    raw_scores: dict[str, int] = {}
    min_possible: dict[str, int] = {}
    max_possible: dict[str, int] = {}
    signed_contribs: dict[str, list[int]] = {}
    counts: dict[str, int] = {}

    # 每个维度在本次试卷中的总权重范围（无论是否作答），
    # 用于计算“权重覆盖程度”：已作答题目权重区间 / 该维度全部题目权重区间。
    total_min_possible: dict[str, int] = {}
    total_max_possible: dict[str, int] = {}
    for q in questions:
        for w in q.weights:
            dim = w.dimension
            total_min_possible[dim] = total_min_possible.get(dim, 0) + min(w.yes, w.no)
            total_max_possible[dim] = total_max_possible.get(dim, 0) + max(w.yes, w.no)

    for q in questions:
        answer = answers.get(q.id)
        if answer not in ("Y", "N"):
            # 未作答的题目不参与任何统计：
            # raw / min / max / 一致性必须基于同一批已作答题目，否则归一化会被
            # 未作答题目的潜在区间"稀释"，分数不再能正确表示价值倾向强度。
            continue
        for w in q.weights:
            dim = w.dimension
            contrib = _contribution(w.yes, w.no, answer)

            raw_scores.setdefault(dim, 0)
            min_possible.setdefault(dim, 0)
            max_possible.setdefault(dim, 0)
            signed_contribs.setdefault(dim, [])
            counts.setdefault(dim, 0)

            raw_scores[dim] += contrib
            min_possible[dim] += min(w.yes, w.no)
            max_possible[dim] += max(w.yes, w.no)
            signed_contribs[dim].append(contrib)
            counts[dim] += 1

    dim_results: dict[str, DimensionResult] = {}
    consistencies: list[float] = []
    uncertain: list[str] = []

    for dim, meta in DIMENSIONS.items():
        if dim not in raw_scores or counts.get(dim, 0) == 0:
            continue  # 本次试卷未覆盖该维度，不输出

        lo, hi = min_possible[dim], max_possible[dim]
        raw = raw_scores[dim]
        if hi > lo:
            normalized = (raw - lo) / (hi - lo) * 100
        else:
            normalized = 50.0
        normalized = round(max(0.0, min(100.0, normalized)), 1)

        consistency = _consistency(signed_contribs[dim])
        if consistency is not None:
            consistencies.append(consistency)
            if consistency < CONSISTENCY_LOW_THRESHOLD:
                uncertain.append(dim)

        tendency, description = _describe(dim, meta, normalized, consistency)

        # 权重覆盖程度：已作答题目权重区间 / 该维度全部题目权重区间（0~1）。
        total_span = total_max_possible.get(dim, hi) - total_min_possible.get(dim, lo)
        answered_span = hi - lo
        weight_coverage = answered_span / total_span if total_span > 0 else 1.0
        confidence = _dimension_confidence(
            question_count=counts[dim],
            consistency=consistency,
            weight_coverage=weight_coverage,
        )

        dim_results[dim] = DimensionResult(
            dimension=dim,
            name=meta["name"],
            raw_score=raw,
            min_possible=lo,
            max_possible=hi,
            score=normalized,
            consistency=consistency,
            tendency=tendency,
            description=description,
            question_count=counts[dim],
            confidence=confidence,
        )

    overall_confidence = round(sum(consistencies) / len(consistencies), 2) if consistencies else 0.0
    conflicts = _conflict_analysis(dim_results)

    return TestResult(
        dimensions=dim_results,
        confidence=overall_confidence,
        conflicts=conflicts,
        uncertain_dimensions=uncertain,
    )


def _dimension_confidence(
    question_count: int,
    consistency: float | None,
    weight_coverage: float,
) -> float:
    """计算单个维度的可信度 (0-1)。

    综合三个信号：
      1. 权重覆盖程度 weight_coverage（0~1）：已作答题目权重区间占比；
      2. 作答一致性 consistency（0~1）：方向越稳定可信度越高，
         样本不足（None）或高度矛盾都会拉低置信度；
      3. 题目数量 quantity（0~1）：低于 MIN_QUESTION_THRESHOLD 时按比例衰减，
         实现“该维度题目数量过少 -> confidence 自动降低”。

    权重：0.5 * 覆盖 + 0.3 * 一致性 + 0.2 * 题量。
    """
    if question_count <= 0:
        return 0.0
    quantity = min(1.0, question_count / MIN_QUESTION_THRESHOLD)
    consistency_factor = consistency if consistency is not None else 0.0
    confidence = 0.5 * weight_coverage + 0.3 * consistency_factor + 0.2 * quantity
    return round(max(0.0, min(1.0, confidence)), 2)


def _consistency(contribs: list[int]) -> float | None:
    """同一维度内多题作答方向的一致程度 (0-1)。

    做法: 记录每题对该维度的作答方向（正贡献取 +1，负贡献取 -1），
    对每个维度比较各题方向的"代数和 |Σ sign|"与"绝对值代数和 Σ|sign|=n"
    的差距：consistency = |Σ sign| / n。

    - 取值 0~1：1 表示所有作答方向完全一致（稳定倾向），
      0 表示同向与反向相互抵消（情境依赖/矛盾）；
    - 只按方向（符号）统计，不受单题权重大小影响，
      避免个别大权重题反向时被过度放大而误判"情境依赖"（过于敏感）；
    - 有效样本 < 2（无信号）时无法判断，返回 None。
    """
    # c == 0 表示该题对当前维度无方向性贡献（如 yes=0, no=5 权重设计），
    # 不计入一致性样本。这避免了"中性贡献"被错误地归入正/负方向。
    signs = [1 if c > 0 else -1 for c in contribs if c != 0]
    if len(signs) < 2:
        return None
    aligned = abs(sum(signs))  # 各题方向代数和
    total = len(signs)         # 各题方向绝对值代数和（每项 |sign| = 1）
    return round(aligned / total, 2)


def _describe(
    dim: str, meta: dict, score: float, consistency: float | None
) -> tuple[str, str]:
    if consistency is not None and consistency < CONSISTENCY_LOW_THRESHOLD:
        return "情境依赖", "该价值维度存在较强情境依赖，不同场景下的选择并不稳定，暂不适合归为单一倾向。"

    if score >= HIGH_SCORE_THRESHOLD:
        return meta["direction"][1], meta["high"]
    if score <= LOW_SCORE_THRESHOLD:
        return meta["direction"][0], meta["low"]
    return "中间地带", f"你在「{meta['direction'][0]} vs {meta['direction'][1]}」之间没有非常明确的倾向，更可能依据具体情境权衡。"


def _conflict_analysis(dim_results: dict[str, DimensionResult]) -> list[dict]:
    """检测典型的高分冲突组合 (docs/ResultInterpretation.md 举例)。"""
    conflicts = []
    for a, b in CONFLICT_PAIRS:
        ra, rb = dim_results.get(a), dim_results.get(b)
        if not ra or not rb:
            continue
        if ra.score >= HIGH_SCORE_THRESHOLD and rb.score >= HIGH_SCORE_THRESHOLD:
            conflicts.append(
                {
                    "dimensions": [a, b],
                    "names": [ra.name, rb.name],
                    "description": (
                        f"你同时展现出较高的「{ra.name}」与「{rb.name}」倾向，"
                        "说明你可能在两者间存在复杂的价值平衡，而非简单地偏向一方。"
                    ),
                }
            )
    return conflicts


def to_api_dimensions(result: TestResult) -> dict[str, float]:
    """[已废弃] 旧版 result 接口的简化字段 {dimension: score}。

    自维度级置信度上线后，result 接口改为返回完整维度对象
    （含 confidence / consistency / question_count 等，见 schemas.DimensionScore），
    本函数保留仅为兼容历史调用，新代码请直接使用 result.dimensions。
    """
    return {d: r.score for d, r in result.dimensions.items()}
