"""scoring.py 单元测试：归一化 (0-100)、min/max possible、一致性。

覆盖修复点：
  1. min/max possible 只基于已作答题目计算（与 raw 同基准），
     保证 score 0-100 正确表示价值倾向强度；
  2. 一致性按"作答方向符号"统计：对每维比较各题方向代数和
     （|Σ sign|）与绝对值代数和（n）的差距，输出 0~1，样本不足返回 None。
"""
import pytest

from app.question_bank import QuestionBank
from app.scoring import _consistency, _dimension_confidence, score_session

# 4 道仅覆盖 altruism 的题，权重两两互为反向，方便手算预期值。
# 单题可能贡献区间 [-3, +3]；4 题全答时 min=-12 / max=+12。
RAW_ALTRUISM = [
    {
        "id": "A1", "content": "q", "type": "YN", "category": "social",
        "difficulty": "easy", "tags": [],
        "weights": [{"dimension": "altruism", "yes": -3, "no": 3}],
        "metadata": {"version": 1, "status": "active"},
    },
    {
        "id": "A2", "content": "q", "type": "YN", "category": "social",
        "difficulty": "easy", "tags": [],
        "weights": [{"dimension": "altruism", "yes": -3, "no": 3}],
        "metadata": {"version": 1, "status": "active"},
    },
    {
        "id": "A3", "content": "q", "type": "YN", "category": "social",
        "difficulty": "easy", "tags": [],
        "weights": [{"dimension": "altruism", "yes": 3, "no": -3}],
        "metadata": {"version": 1, "status": "active"},
    },
    {
        "id": "A4", "content": "q", "type": "YN", "category": "social",
        "difficulty": "easy", "tags": [],
        "weights": [{"dimension": "altruism", "yes": 3, "no": -3}],
        "metadata": {"version": 1, "status": "active"},
    },
]


@pytest.fixture
def altruism_bank():
    bank = QuestionBank.from_raw(RAW_ALTRUISM, source="test")
    return bank, bank.active_questions()


# ---------------------------------------------------------------------------
# 归一化
# ---------------------------------------------------------------------------


def test_normalization_midpoint(altruism_bank):
    """raw=0 -> 50 分（价值倾向强度居中的中性位置）。"""
    _, questions = altruism_bank
    answers = {"A1": "Y", "A2": "N", "A3": "Y", "A4": "N"}
    r = score_session(questions, answers).dimensions["altruism"]
    assert r.min_possible == -12
    assert r.max_possible == 12
    assert r.raw_score == 0
    assert r.score == 50.0


def test_normalization_high(altruism_bank):
    """全部指向 direction[1] -> 100 分。"""
    _, questions = altruism_bank
    answers = {"A1": "N", "A2": "N", "A3": "Y", "A4": "Y"}
    r = score_session(questions, answers).dimensions["altruism"]
    assert r.raw_score == 12
    assert r.score == 100.0


def test_normalization_low(altruism_bank):
    """全部指向 direction[0] -> 0 分。"""
    _, questions = altruism_bank
    answers = {"A1": "Y", "A2": "Y", "A3": "N", "A4": "N"}
    r = score_session(questions, answers).dimensions["altruism"]
    assert r.raw_score == -12
    assert r.score == 0.0


def test_normalization_uses_only_answered_questions(altruism_bank):
    """回归测试：min/max 只应基于已作答题目。

    只作答 A1/A2（贡献 -3 各一）时：
      - 修复前：min/max 按全部 4 题算（-12/12），raw=-6 -> 25 分（错误）；
      - 修复后：min/max 只按已作答 2 题算（-6/6），raw=-6 -> 0 分。
    """
    _, questions = altruism_bank
    answers = {"A1": "Y", "A2": "Y"}
    r = score_session(questions, answers).dimensions["altruism"]
    assert r.question_count == 2
    assert r.min_possible == -6
    assert r.max_possible == 6
    assert r.raw_score == -6
    assert r.score == 0.0


def test_normalization_score_bounded_0_100(altruism_bank):
    _, questions = altruism_bank
    answers = {"A1": "N", "A2": "Y", "A3": "N", "A4": "Y"}
    r = score_session(questions, answers).dimensions["altruism"]
    assert 0.0 <= r.score <= 100.0


# ---------------------------------------------------------------------------
# 一致性
# ---------------------------------------------------------------------------


def test_consistency_direction_based():
    """一致性按作答方向（符号）统计，不受权重大小影响。"""
    assert _consistency([5, 5]) == 1.0        # 完全一致
    assert _consistency([5, -5]) == 0.0       # 完全抵消
    assert _consistency([1, 1, -1, -1]) == 0.0
    # 各题方向代数和 vs 绝对值代数和：|Σ sign| / n
    assert _consistency([5, 3, -1]) == round(1 / 3, 2)    # 2 同 1 反
    assert _consistency([5, -1, -1]) == round(1 / 3, 2)   # 1 同 2 反
    # 权重大小不放大敏感度：大权重反向也只算一个方向
    assert _consistency([5, -5, -1]) == round(1 / 3, 2)
    assert _consistency([5, 5, -1]) == round(1 / 3, 2)
    # 8/9 同向不应被判为情境依赖（修复"过于敏感"）
    assert _consistency([5, 5, 5, 5, 5, 5, 5, 5, -5]) == round(7 / 9, 2)


def test_consistency_insufficient_samples():
    """有效样本不足时返回 None。"""
    assert _consistency([]) is None
    assert _consistency([5]) is None
    assert _consistency([0, 5]) is None
    assert _consistency([0, 0]) is None


def test_consistency_output_range():
    for contribs in ([5, 4], [5, -4], [3, 1, -2], [1, 2, 3, -6]):
        value = _consistency(contribs)
        assert value is not None
        assert 0.0 <= value <= 1.0


def test_consistency_low_marks_uncertain(altruism_bank):
    """低一致性维度应进入 uncertain_dimensions。"""
    _, questions = altruism_bank
    answers = {"A1": "Y", "A2": "Y", "A3": "N", "A4": "N"}  # 全部指向 direction[0]
    # 上面是完全一致（1.0），不会 uncertain；构造矛盾作答：
    answers = {"A1": "Y", "A2": "N", "A3": "N", "A4": "Y"}  # contribs: -3,+3,-3,+3
    result = score_session(questions, answers)
    assert result.dimensions["altruism"].consistency == 0.0
    assert "altruism" in result.uncertain_dimensions


# ---------------------------------------------------------------------------
# 维度级置信度 confidence
# ---------------------------------------------------------------------------

FULL_CONSISTENT = {"A1": "N", "A2": "N", "A3": "Y", "A4": "Y"}  # 全答且方向一致
FULL_CONTRADICT = {"A1": "Y", "A2": "N", "A3": "N", "A4": "Y"}  # 全答但矛盾
PARTIAL_2Q = {"A1": "Y", "A2": "Y"}  # 只答一半


def test_dimension_confidence_in_range(altruism_bank):
    """维度结果包含 confidence 且范围在 0~1。"""
    _, questions = altruism_bank
    r = score_session(questions, FULL_CONSISTENT).dimensions["altruism"]
    assert 0.0 <= r.confidence <= 1.0
    # 全答且一致 -> 高置信度
    assert r.confidence > 0.5


def test_dimension_confidence_penalizes_contradiction(altruism_bank):
    """高度矛盾的回答会拉低 confidence。"""
    _, questions = altruism_bank
    consistent = score_session(questions, FULL_CONSISTENT).dimensions["altruism"]
    contradict = score_session(questions, FULL_CONTRADICT).dimensions["altruism"]
    assert contradict.confidence < consistent.confidence


def test_dimension_confidence_penalizes_few_questions(altruism_bank):
    """同等作答质量下，题量/权重覆盖不足会拉低 confidence。"""
    _, questions = altruism_bank
    full = score_session(questions, FULL_CONSISTENT).dimensions["altruism"]
    partial = score_session(questions, PARTIAL_2Q).dimensions["altruism"]
    assert partial.question_count == 2
    assert full.question_count == 4
    assert partial.confidence < full.confidence


def test_dimension_confidence_quantity_factor():
    """相同一致性/覆盖下，题量越少 confidence 越低（<5 时自动衰减）。"""
    low = _dimension_confidence(
        question_count=2, consistency=0.5, weight_coverage=0.5
    )
    high = _dimension_confidence(
        question_count=8, consistency=0.5, weight_coverage=0.5
    )
    assert low < high
    assert low < 0.5


def test_dimension_confidence_zero_when_no_answers():
    """无作答题目时 confidence 为 0。"""
    assert _dimension_confidence(question_count=0, consistency=None, weight_coverage=0.0) == 0.0


def test_dimension_confidence_bounded_0_1():
    """confidence 始终落在 0~1。"""
    for args in (
        dict(question_count=0, consistency=None, weight_coverage=0.0),
        dict(question_count=50, consistency=1.0, weight_coverage=1.0),
        dict(question_count=3, consistency=0.0, weight_coverage=0.2),
    ):
        value = _dimension_confidence(**args)
        assert 0.0 <= value <= 1.0
