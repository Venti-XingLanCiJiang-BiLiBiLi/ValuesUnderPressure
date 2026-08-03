"""selection.py 单元测试：锚定题随机化 + seed 可复现 + 分层组卷。

覆盖修复点：
  - 锚定题从 must 池随机抽样（不再固定取 id 排序后前 N 道）；
  - 相同 seed 下试卷与锚定题均可复现。
"""
import random

import pytest

from app.question_bank import load_question_bank
from app.selection import ANCHOR_COUNT, _anchor_questions, build_test


@pytest.fixture(scope="module")
def bank():
    return load_question_bank()


# ---------------------------------------------------------------------------
# 锚定题
# ---------------------------------------------------------------------------


def test_anchor_reproducible_with_same_seed(bank):
    a1 = _anchor_questions(bank, ANCHOR_COUNT, random.Random(7))
    a2 = _anchor_questions(bank, ANCHOR_COUNT, random.Random(7))
    assert [q.id for q in a1] == [q.id for q in a2]


def test_anchor_randomized_across_seeds(bank):
    """不同 seed 应得到不同锚定题组合（而非固定前 N 道）。"""
    combos = {
        tuple(sorted(q.id for q in _anchor_questions(bank, ANCHOR_COUNT, random.Random(s))))
        for s in range(12)
    }
    assert len(combos) > 1


def test_anchor_are_must_questions(bank):
    for s in range(5):
        anchors = _anchor_questions(bank, ANCHOR_COUNT, random.Random(s))
        assert len(anchors) == ANCHOR_COUNT
        assert all(q.category == "must" for q in anchors)


def test_anchor_handles_count_beyond_pool(bank):
    """数量超过 must 池时返回全部 must 题，不报错。"""
    all_must = bank.by_category("must")
    anchors = _anchor_questions(bank, len(all_must) + 5, random.Random(1))
    assert {q.id for q in anchors} == {q.id for q in all_must}


# ---------------------------------------------------------------------------
# 整卷组卷
# ---------------------------------------------------------------------------


def test_build_test_reproducible_with_seed(bank):
    t1 = build_test(bank, length=20, seed=42)
    t2 = build_test(bank, length=20, seed=42)
    assert [q.id for q in t1] == [q.id for q in t2]
    assert len(t1) == len(t2) == 20


def test_build_test_length(bank):
    qs = build_test(bank, length=10, seed=1)
    assert len(qs) == 10


def test_build_test_no_duplicate_questions(bank):
    qs = build_test(bank, length=20, seed=3)
    ids = [q.id for q in qs]
    assert len(ids) == len(set(ids))


def test_build_test_includes_anchors(bank):
    """锚定题必须出现在生成的试卷中。"""
    seed = 11
    rng = random.Random(seed)
    anchors = _anchor_questions(bank, min(ANCHOR_COUNT, 20 // 8), rng)
    qs = build_test(bank, length=20, seed=seed)
    selected_ids = {q.id for q in qs}
    assert {q.id for q in anchors}.issubset(selected_ids)
