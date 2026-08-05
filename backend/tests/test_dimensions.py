"""dimensions.py 维度元数据加载测试（题库 dimensions.json 单一数据源）。

覆盖：
  - DIMENSIONS 从题库加载（10 个核心维度、字段完整）
  - reload_dimensions 就地更新、引用稳定、DIMENSION_IDS 同步
  - 开发环境题库缺少 dimensions.json 时回退内置默认不崩溃
  - 生产环境（APP_ENV=production|prod）题库缺少 dimensions.json 时禁止回退、必须抛错
"""
import json

import pytest

from app import dimensions
from app.dimensions import DIMENSION_IDS, DIMENSIONS, reload_dimensions

CORE_IDS = {
    "self_protection", "altruism", "freedom", "security", "privacy",
    "wealth", "rule_orientation", "pragmatism", "collectivism", "long_term",
}
REQUIRED_KEYS = (
    "abbr", "label", "description",
    "low_score_label", "low_score_description",
    "high_score_label", "high_score_description",
)
# 兼容别名：由规范字段在加载时派生，历史调用方依赖
LEGACY_ALIAS_KEYS = ("name", "direction", "high", "low")


def _restore(monkeypatch):
    """撤销 patch 并从真实题库重载（同时同步 DIMENSION_IDS），避免污染全局状态。"""
    monkeypatch.undo()
    reload_dimensions()


def test_dimensions_loaded_from_bank_file():
    """DIMENSIONS 来自题库 dimensions.json：10 个核心维度且字段完整。"""
    assert set(DIMENSIONS.keys()) == CORE_IDS
    for dim, meta in DIMENSIONS.items():
        for key in REQUIRED_KEYS:
            assert key in meta, f"维度 {dim} 缺少字段: {key}"
        for key in LEGACY_ALIAS_KEYS:
            assert key in meta, f"维度 {dim} 缺少兼容别名: {key}"
        assert meta["name"] == meta["label"]
        assert meta["direction"] == [meta["low_score_label"], meta["high_score_label"]]
        assert meta["high"] == meta["high_score_description"]
        assert meta["low"] == meta["low_score_description"]


def test_dimension_ids_matches_keys():
    assert DIMENSION_IDS == list(DIMENSIONS.keys())


def test_dimensions_carry_chinese_labels():
    """英文维度 ID → 中文标签/高低分表现映射随题库提供（网页展示用）。"""
    assert DIMENSIONS["self_protection"]["label"] == "自我保护"
    assert DIMENSIONS["self_protection"]["name"] == "自我保护"  # 兼容别名
    assert DIMENSIONS["altruism"]["direction"] == ["自我优先", "利他优先"]
    assert DIMENSIONS["privacy"]["low_score_label"] == "开放共享"
    assert DIMENSIONS["privacy"]["high_score_label"] == "隐私保护"
    assert DIMENSIONS["privacy"]["low_score_description"]
    assert DIMENSIONS["privacy"]["high_score_description"]


def test_reload_dimensions_in_place(monkeypatch):
    """reload_dimensions 就地更新：对象引用稳定、新维度生效、DIMENSION_IDS 同步。"""
    meta = {
        "new_dim": {
            "abbr": "ND",
            "label": "新维度",
            "description": "占位描述",
            "low_score_label": "低端",
            "low_score_description": "低端文案",
            "high_score_label": "高端",
            "high_score_description": "高端文案",
        },
    }
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        monkeypatch.setattr(dimensions, "resolve_bank_dir", lambda: tmp)
        with open(f"{tmp}/dimensions.json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)
        before_ref = DIMENSIONS
        reloaded = reload_dimensions()
        assert reloaded is before_ref  # 就地更新，保持引用
        assert set(DIMENSIONS.keys()) == {"new_dim"}
        assert DIMENSION_IDS == ["new_dim"]
        # 规范字段 + 兼容别名都被补齐
        assert DIMENSIONS["new_dim"]["label"] == "新维度"
        assert DIMENSIONS["new_dim"]["name"] == "新维度"
        assert DIMENSIONS["new_dim"]["direction"] == ["低端", "高端"]
    _restore(monkeypatch)


def test_load_fallback_on_missing_file(tmp_path, monkeypatch):
    """开发环境题库目录缺少 dimensions.json 时回退内置默认，不崩溃。"""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setattr(dimensions, "resolve_bank_dir", lambda: str(tmp_path))
    dimensions._load_dimensions()
    assert len(DIMENSIONS) == 10
    assert "self_protection" in DIMENSIONS
    _restore(monkeypatch)


def test_load_fallback_on_missing_file_default_env(tmp_path, monkeypatch):
    """未设置 APP_ENV（默认开发）时缺少 dimensions.json 仍可回退，保持既有行为。"""
    monkeypatch.delenv("APP_ENV", raising=False)
    monkeypatch.setattr(dimensions, "resolve_bank_dir", lambda: str(tmp_path))
    dimensions._load_dimensions()
    assert len(DIMENSIONS) == 10
    _restore(monkeypatch)


@pytest.mark.parametrize("env", ["production", "prod"])
def test_load_raises_when_missing_in_production(tmp_path, monkeypatch, env):
    """生产环境缺少 dimensions.json 时禁止回退，必须抛明确异常。"""
    monkeypatch.setenv("APP_ENV", env)
    monkeypatch.setattr(dimensions, "resolve_bank_dir", lambda: str(tmp_path))
    with pytest.raises(FileNotFoundError) as exc:
        dimensions._load_dimensions()
    msg = str(exc.value)
    assert "dimensions.json" in msg        # 缺失文件路径
    assert "禁止回退" in msg                # 明确禁止回退语义
    assert "修复建议" in msg                # 含修复建议
    _restore(monkeypatch)


def test_load_raises_when_corrupt_json_in_production(tmp_path, monkeypatch):
    """生产环境 dimensions.json JSON 非法时禁止回退，必须抛异常。"""
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setattr(dimensions, "resolve_bank_dir", lambda: str(tmp_path))
    (tmp_path / "dimensions.json").write_text("{invalid json", encoding="utf-8")
    with pytest.raises(RuntimeError) as exc:
        dimensions._load_dimensions()
    msg = str(exc.value)
    assert "禁止回退" in msg
    assert "修复建议" in msg
    _restore(monkeypatch)


def test_load_raises_when_invalid_structure_in_production(tmp_path, monkeypatch):
    """生产环境 dimensions.json 结构不符时禁止回退，必须抛异常。"""
    monkeypatch.setenv("APP_ENV", "prod")
    monkeypatch.setattr(dimensions, "resolve_bank_dir", lambda: str(tmp_path))
    (tmp_path / "dimensions.json").write_text(
        json.dumps({"broken": {"no_required_fields": True}}), encoding="utf-8"
    )
    with pytest.raises(RuntimeError) as exc:
        dimensions._load_dimensions()
    msg = str(exc.value)
    assert "禁止回退" in msg
    assert "修复建议" in msg
    _restore(monkeypatch)
