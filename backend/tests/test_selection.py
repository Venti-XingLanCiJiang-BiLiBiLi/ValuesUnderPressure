"""selection.py 单元测试：must 桶抽题 + seed 可复现 + 分类配额 + 难度分层。

覆盖需求：
  - must 题按顺序每 4 题一桶，每桶抽 1 题得到候选，再从候选中随机取 5 题；
  - experimental 固定抽 1 题；
  - 其余 10 个常规分类每个随机抽 4~5 题（默认 50 题合计 44 题）；
  - 常规分类内按难度（easy/medium/hard）比例分层采样；
  - 整卷默认 50 题，相同 seed 下可复现。

组卷规则依赖完整的 12 分类题库，因此本文件直接使用正式题库
（question-bank/questions.json，绕过 conftest 的精简 fixture）。
"""
import random
from collections import Counter

import pytest

from app.question_bank import PRODUCTION_BANK_PATH, load_question_bank
from app.selection import (
    DEFAULT_LENGTH,
    DIFFICULTY_ORDER,
    EXPERIMENTAL_TARGET,
    MUST_BUCKET_SIZE,
    MUST_TARGET,
    REGULAR_CATEGORIES,
    _must_buckets,
    _must_candidates,
    _pick_must,
    _split_quota_by_difficulty,
    build_test,
)


@pytest.fixture(scope="module")
def bank():
    return load_question_bank(path=PRODUCTION_BANK_PATH)


# ---------------------------------------------------------------------------
# must 桶抽题
# ---------------------------------------------------------------------------


def test_must_buckets_keep_order_and_size(bank):
    """must 题按题库顺序每 4 题一桶。"""
    buckets = _must_buckets(bank)
    flat = [q.id for b in buckets for q in b]
    assert flat == sorted(flat)
    assert all(len(b) == MUST_BUCKET_SIZE for b in buckets)


def test_must_one_per_bucket(bank):
    """每桶恰好抽 1 题。"""
    rng = random.Random(7)
    candidates = _must_candidates(bank, rng)
    assert len(candidates) == len(_must_buckets(bank))
    for bucket, q in zip(_must_buckets(bank), candidates):
        assert q.id in {x.id for x in bucket}


def test_pick_must_target_count(bank):
    """从候选中随机取 MUST_TARGET 题，且都是 must 题。"""
    picked = _pick_must(bank, random.Random(3))
    assert len(picked) == MUST_TARGET
    assert all(q.category == "must" for q in picked)


def test_pick_must_reproducible_with_same_seed(bank):
    a1 = _pick_must(bank, random.Random(7))
    a2 = _pick_must(bank, random.Random(7))
    assert [q.id for q in a1] == [q.id for q in a2]


def test_pick_must_randomized_across_seeds(bank):
    """不同 seed 应得到不同的 must 组合（而非固定取某几题）。"""
    combos = {
        tuple(sorted(q.id for q in _pick_must(bank, random.Random(s))))
        for s in range(12)
    }
    assert len(combos) > 1


# ---------------------------------------------------------------------------
# 难度分层
# ---------------------------------------------------------------------------


def test_split_quota_by_difficulty_sums_to_quota():
    """配额拆分后总和恒等于 quota，且所有值非负。"""
    available = {"easy": 7, "medium": 2, "hard": 6}
    for quota in (1, 2, 3, 4, 5, 10):
        alloc = _split_quota_by_difficulty(available, quota)
        assert sum(alloc.values()) == quota
        assert all(v >= 0 for v in alloc.values())
        assert set(alloc) == set(DIFFICULTY_ORDER)


def test_split_quota_by_difficulty_proportional():
    """按比例分配：稀缺难度不会被过度采样。"""
    # total=15, quota=5 -> 理想 easy≈2.33 medium≈0.67 hard≈2（最大余数法）
    alloc = _split_quota_by_difficulty({"easy": 7, "medium": 2, "hard": 6}, 5)
    assert alloc == {"easy": 2, "medium": 1, "hard": 2}


def test_split_quota_by_difficulty_empty_pool():
    alloc = _split_quota_by_difficulty({"easy": 0, "medium": 0, "hard": 0}, 5)
    assert alloc == {"easy": 0, "medium": 0, "hard": 0}


def test_split_quota_by_difficulty_single_difficulty():
    """只有单一难度可用时，配额全部落入该难度。"""
    alloc = _split_quota_by_difficulty({"easy": 3, "medium": 0, "hard": 0}, 4)
    assert alloc["easy"] == 4
    assert alloc["medium"] == 0 and alloc["hard"] == 0


def test_build_test_regular_difficulty_stratified(bank):
    """常规分类按难度分层：整卷常规部分三种难度均出现，且非单一难度堆叠。"""
    for seed in (1, 5, 42):
        qs = [q for q in build_test(bank, seed=seed) if q.category in REGULAR_CATEGORIES]
        diffs = Counter(q.difficulty for q in qs)
        assert len(diffs) == 3
        assert all(diffs[d] >= 1 for d in DIFFICULTY_ORDER)


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
    """默认 50 题组成: must 5 + experimental 1 + 常规分类 44。"""
    qs = build_test(bank, seed=3)
    cats = Counter(q.category for q in qs)
    assert cats["must"] == MUST_TARGET
    assert cats["experimental"] == EXPERIMENTAL_TARGET
    regular_total = sum(cats[c] for c in REGULAR_CATEGORIES)
    assert regular_total == DEFAULT_LENGTH - MUST_TARGET - EXPERIMENTAL_TARGET
    assert all(4 <= cats[c] <= 5 for c in REGULAR_CATEGORIES)


def test_build_test_regular_quota_distribution(bank):
    """默认 50 题时: 恰好 4 个分类抽 5 题、6 个分类抽 4 题。"""
    cats = Counter(q.category for q in build_test(bank, seed=5))
    counts = [cats[c] for c in REGULAR_CATEGORIES]
    assert counts.count(5) == 4
    assert counts.count(4) == 6


def test_build_test_no_duplicate_questions(bank):
    qs = build_test(bank, seed=3)
    ids = [q.id for q in qs]
    assert len(ids) == len(set(ids))


def test_build_test_scales_with_length(bank):
    """非默认长度按比例缩放常规分类配额，总数等于 length。"""
    for length in (20, 60):
        qs = build_test(bank, length=length, seed=2)
        assert len(qs) == length
        cats = Counter(q.category for q in qs)
        assert cats["must"] == MUST_TARGET
        assert cats["experimental"] == EXPERIMENTAL_TARGET
