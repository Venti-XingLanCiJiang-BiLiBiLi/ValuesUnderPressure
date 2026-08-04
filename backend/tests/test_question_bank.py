"""question_bank.py 单元测试：生产禁止静默回退 / 开发允许回退。

覆盖修复点：
  - APP_ENV=production|prod 时正式题库缺失必须抛 FileNotFoundError，
    即使开发样例存在也不得回退；
  - 开发环境（默认/development）允许回退到内置样例题库。
"""
import json

import pytest

from app import question_bank as qb

# 本模块用例专测已弃用的兼容 API（load_question_bank）行为，属于兼容回归保护，
# 保留 API 本身，仅抑制其 DeprecationWarning，避免测试输出被警告刷屏。
pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


def _valid_question(qid="Q1"):
    return {
        "id": qid,
        "content": "question",
        "type": "YN",
        "category": "social",
        "difficulty": "easy",
        "tags": [],
        "weights": [{"dimension": "altruism", "yes": -3, "no": 3}],
        "metadata": {"version": 1, "status": "active"},
    }


@pytest.fixture
def bank_paths(tmp_path, monkeypatch):
    """把生产题库指向不存在的路径，把开发回退指向一个临时样例。"""
    missing = tmp_path / "missing" / "questions.json"
    fallback = tmp_path / "fallback.json"
    fallback.write_text(json.dumps([_valid_question("F1")]), encoding="utf-8")
    monkeypatch.setattr(qb, "PRODUCTION_BANK_PATH", str(missing))
    monkeypatch.setattr(qb, "FALLBACK_BANK_PATH", str(fallback))
    monkeypatch.delenv("QUESTION_BANK_PATH", raising=False)
    return missing, fallback


def test_production_raises_when_bank_missing(bank_paths, monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    with pytest.raises(FileNotFoundError):
        qb.load_question_bank()


def test_production_raises_even_when_fallback_exists(bank_paths, monkeypatch):
    """生产环境即使开发样例存在也禁止静默回退。"""
    monkeypatch.setenv("APP_ENV", "prod")
    with pytest.raises(FileNotFoundError):
        qb.load_question_bank()


def test_development_falls_back_to_sample(bank_paths, monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    bank = qb.load_question_bank()
    assert bank.source == str(bank_paths[1])
    assert len(bank.questions) == 1


def test_default_environment_allows_fallback(bank_paths, monkeypatch):
    """未设置 APP_ENV（默认开发）时允许回退，保持既有行为。"""
    monkeypatch.delenv("APP_ENV", raising=False)
    bank = qb.load_question_bank()
    assert bank.source == str(bank_paths[1])


def test_production_loads_existing_bank(tmp_path, monkeypatch):
    """生产环境正式题库存在时应正常加载，而非报错。"""
    prod = tmp_path / "prod" / "questions.json"
    prod.parent.mkdir(parents=True)
    prod.write_text(
        json.dumps([_valid_question("P1"), _valid_question("P2")]), encoding="utf-8"
    )
    fallback = tmp_path / "fallback.json"
    fallback.write_text(json.dumps([_valid_question("F1")]), encoding="utf-8")
    monkeypatch.setattr(qb, "PRODUCTION_BANK_PATH", str(prod))
    monkeypatch.setattr(qb, "FALLBACK_BANK_PATH", str(fallback))
    monkeypatch.delenv("QUESTION_BANK_PATH", raising=False)
    monkeypatch.setenv("APP_ENV", "production")
    bank = qb.load_question_bank()
    assert bank.source == str(prod)
    assert len(bank.questions) == 2
