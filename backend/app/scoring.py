"""
评分算法实现。

来源:
  docs/ScoringAlgorithm.md  -> 累加 + 归一化(0-100) + 一致性分析
  docs/ResultInterpretation.md -> 倾向方向 / 典型行为描述 / 矛盾分析 / 不确定性
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .dimensions import DIMENSIONS, CONFLICT_PAIRS
from .question_bank import Question

CONSISTENCY_LOW_THRESHOLD = 0.5
# 倾向分类阈值与前端 bar 颜色阈值（frontend/src/config/theme.ts SCORE_THRESHOLDS）对齐：
# >= 60 高分倾向 / <= 40 低分倾向 / 40~60 中间地带
HIGH_SCORE_THRESHOLD = 60
LOW_SCORE_THRESHOLD = 40


@dataclass
class DimensionResult:
    dimension: str
    name: str
    raw_score: int
    min_possible: int
    max_possible: int
    score: float  # 0-100 归一化分数
    consistency: Optional[float]  # 0-1，None 表示样本不足
    tendency: str  # 描述方向的文字
    description: str
    question_count: int


@dataclass
class TestResult:
    dimensions: Dict[str, DimensionResult]
    confidence: float
    conflicts: List[dict]
    uncertain_dimensions: List[str]


def _contribution(weight_yes: int, weight_no: int, answer: str) -> int:
    return weight_yes if answer == "Y" else weight_no


def score_session(
    questions: List[Question], answers: Dict[str, str]
) -> TestResult:
    """根据已作答的题目计算各维度得分、一致性与矛盾分析。

    answers: {question_id: "Y" | "N"}，只统计已回答的题目。
    """
    by_id = {q.id: q for q in questions}

    raw_scores: Dict[str, int] = {}
    min_possible: Dict[str, int] = {}
    max_possible: Dict[str, int] = {}
    signed_contribs: Dict[str, List[int]] = {}
    counts: Dict[str, int] = {}

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

    dim_results: Dict[str, DimensionResult] = {}
    consistencies: List[float] = []
    uncertain: List[str] = []

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
        )

    overall_confidence = round(sum(consistencies) / len(consistencies), 2) if consistencies else 0.0
    conflicts = _conflict_analysis(dim_results)

    return TestResult(
        dimensions=dim_results,
        confidence=overall_confidence,
        conflicts=conflicts,
        uncertain_dimensions=uncertain,
    )


def _consistency(contribs: List[int]) -> Optional[float]:
    """同一维度内多题作答方向的一致程度 (0-1)。

    做法: 把每题贡献值按其权重大小进行合成——
    consistency = |Σ contrib| / Σ|contrib|。

    - 取值 0~1：1 表示所有作答方向完全一致（高一致性），
      0 表示正负贡献相互抵消（情境依赖/矛盾）；
    - 贡献绝对值越大，对一致性影响越大（考虑了权重大小，而非只数符号）；
    - 有效样本 < 2（或总贡献为 0，无信号）时无法判断，返回 None。
    """
    nonzero = [c for c in contribs if c != 0]
    if len(nonzero) < 2:
        return None
    total_magnitude = sum(abs(c) for c in nonzero)
    if total_magnitude == 0:
        return None
    aligned = abs(sum(nonzero))
    return round(aligned / total_magnitude, 2)


def _describe(
    dim: str, meta: dict, score: float, consistency: Optional[float]
) -> Tuple[str, str]:
    if consistency is not None and consistency < CONSISTENCY_LOW_THRESHOLD:
        return "情境依赖", "该价值维度存在较强情境依赖，不同场景下的选择并不稳定，暂不适合归为单一倾向。"

    if score >= HIGH_SCORE_THRESHOLD:
        return meta["direction"][1], meta["high"]
    if score <= LOW_SCORE_THRESHOLD:
        return meta["direction"][0], meta["low"]
    return "中间地带", f"你在「{meta['direction'][0]} vs {meta['direction'][1]}」之间没有非常明确的倾向，更可能依据具体情境权衡。"


def _conflict_analysis(dim_results: Dict[str, DimensionResult]) -> List[dict]:
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


def to_api_dimensions(result: TestResult) -> Dict[str, float]:
    """docs/API.md 中 result 接口的简化字段: {dimension: score}"""
    return {d: r.score for d, r in result.dimensions.items()}
