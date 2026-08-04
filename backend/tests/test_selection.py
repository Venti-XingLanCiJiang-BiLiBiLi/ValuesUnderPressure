"""selection.py 单元测试：桶驱动抽题（依赖分桶索引）+ seed 可复现 + 配额分布 + 无重复。

覆盖需求：
  - 抽题依赖分桶索引（BucketBank）懒加载桶文件，不加载全量题库；
  - 某组（m 桶、d 题）抽 n 题：先抽 k=min(n,m) 桶；候选不足 n 题时重复抽桶补充；
    桶内随机取题不重复；
  - d < n 时按 fallback 补齐；
  - must / experimental 特殊组抽题；
  - 整卷默认 50 题、相同 seed 可复现、无重复题。

组卷规则依赖完整题库，本文件直接使用正式题库的分桶索引
（question-bank/v1/questions.index.json，绕过 conftest 的精简 fixture）。
"""
import os
import random

import pytest

from app.question_bank import BucketBank, resolve_bank_dir
from app.selection import (
    DEFAULT_LENGTH,
    EXPERIMENTAL_TARGET,
    MUST_TARGET,
    _draw_from_group,
    build_test,
)


INDEX_PATH = os.path.join(resolve_bank_dir(), "questions.index.json")


@pytest.fixture(scope="module")
def bank():
    assert os.path.isfile(INDEX_PATH), f"缺少分桶索引: {INDEX_PATH}"
    return BucketBank.from_index_file(INDEX_PATH)


def _make_bank(raws, bucket_size=2):
    """从原始题目列表构建虚拟 BucketBank，便于测试边界场景。"""
    return BucketBank.from_questions(raws, bucket_size=bucket_size)


def _raw(qid, dim, bucket):
    return {
        "id": qid,
        "content": f"question {qid}",
        "type": "YN",
        "category": "social",
        "difficulty": "easy",
        "tags": [dim],
        "weights": [{"dimension": dim, "yes": bucket, "no": -bucket}],
        "metadata": {"version": 1, "status": "active"},
    }


# ---------------------------------------------------------------------------
# _draw_from_group：桶驱动抽题
# ---------------------------------------------------------------------------


def test_draw_from_group_picks_n_unique(bank):
    """从正式维度组（10 桶 40 题）抽 5 题：恰好 5 题、无重复、均属该主维度。"""
    group = bank.group("self_protection")
    picked = _draw_from_group(group, 5, random.Random(1), bank, set())
    ids = [q.id for q in picked]
    assert len(picked) == 5
    assert len(ids) == len(set(ids))
    assert all(q.weights[0].dimension == "self_protection" for q in picked)


def test_draw_from_group_respects_exclude_ids(bank):
    """排除已选题后，不会抽到 exclude_ids 中的题。"""
    group = bank.group("altruism")
    exclude = {q.id for q in bank.questions_in_group("altruism")[:5]}
    picked = _draw_from_group(group, 3, random.Random(2), bank, exclude)
    assert all(q.id not in exclude for q in picked)


def test_draw_from_group_n_greater_than_bucket_count():
    """n > m（要抽的题数超过桶数）时：先抽全部 m 桶，再从中随机取 n 题。"""
    # 6 题 / 每桶 2 题 = 3 桶，d=6，n=4 > m=3
    raws = [
        _raw("T01", "freedom", 1), _raw("T02", "freedom", 2),
        _raw("T03", "freedom", 3), _raw("T04", "freedom", 4),
        _raw("T05", "freedom", 5), _raw("T06", "freedom", -1),
    ]
    b = _make_bank(raws, bucket_size=2)
    group = b.group("freedom")
    assert len(group["files"]) == 3
    picked = _draw_from_group(group, 4, random.Random(7), b, set())
    assert len(picked) == 4
    assert len({q.id for q in picked}) == 4


def test_draw_from_group_d_less_than_n_returns_all():
    """d < n 时：返回该组全部可用题（上层按 fallback 补齐）。"""
    raws = [_raw("T01", "freedom", 1), _raw("T02", "freedom", 2)]
    b = _make_bank(raws, bucket_size=2)  # d=2, m=1
    group = b.group("freedom")
    picked = _draw_from_group(group, 3, random.Random(1), b, set())
    assert len(picked) == 2  # 只有 2 题可抽


def test_draw_from_group_reproducible_with_seed(bank):
    group = bank.group("wealth")
    a1 = _draw_from_group(group, 5, random.Random(9), bank, set())
    a2 = _draw_from_group(group, 5, random.Random(9), bank, set())
    assert [q.id for q in a1] == [q.id for q in a2]


# ---------------------------------------------------------------------------
# 整卷组卷
# ---------------------------------------------------------------------------


def test_build_test_default_length_is_50(bank):
    qs = build_test(bank, seed=1)
    assert len(qs) == DEFAULT_LENGTH == 50


def test_build_test_reproducible_with_seed(bank):
    t1 = build_test(bank, seed=42)
    t2 = build_test(bank, seed=42)
    assert [q.id for q in t1] == [q.id for q in t2]
    assert len(t1) == len(t2) == DEFAULT_LENGTH


def test_build_test_composition(bank):
    """默认 50 题组成: must 5 + experimental 1 + 常规维度 44。"""
    qs = build_test(bank, seed=3)
    must_count = sum(1 for q in qs if q.category == "must")
    exp_count = sum(1 for q in qs if q.category == "experimental")
    regular = len(qs) - must_count - exp_count
    assert must_count == MUST_TARGET
    assert exp_count == EXPERIMENTAL_TARGET
    assert regular == DEFAULT_LENGTH - MUST_TARGET - EXPERIMENTAL_TARGET


def test_build_test_regular_quota_distribution(bank):
    """默认 50 题时: 常规部分恰好 4 个维度抽 5 题、6 个维度抽 4 题。"""
    from collections import Counter

    qs = build_test(bank, seed=5)
    primary = Counter(
        q.weights[0].dimension for q in qs if q.category not in ("must", "experimental")
    )
    counts = [primary[d] for d in primary]
    assert counts.count(5) == 4
    assert counts.count(4) == 6


def test_build_test_no_duplicate_questions(bank):
    qs = build_test(bank, seed=3)
    ids = [q.id for q in qs]
    assert len(ids) == len(set(ids))


def test_build_test_scales_with_length(bank):
    """非默认长度按比例缩放常规维度配额，总数等于 length。"""
    for length in (20, 60):
        qs = build_test(bank, length=length, seed=2)
        assert len(qs) == length
        must_count = sum(1 for q in qs if q.category == "must")
        exp_count = sum(1 for q in qs if q.category == "experimental")
        assert must_count == MUST_TARGET
        assert exp_count == EXPERIMENTAL_TARGET


def test_build_test_dimension_filter(bank):
    """指定 dimensions 时，试卷只包含匹配指定维度的题目。"""
    qs = build_test(bank, length=30, dimensions=["privacy"], seed=4)
    assert all("privacy" in [w.dimension for w in q.weights] for q in qs)
    assert len(qs) == 30

