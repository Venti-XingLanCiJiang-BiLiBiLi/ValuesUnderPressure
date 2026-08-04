"""manifest 机制测试（backend/app/manifest.py）。

覆盖：
  - 正常 manifest 验证通过
  - 修改 questions.json 后 hash 校验失败
  - 修改 dimensions.json 后 hash 校验失败
  - manifest 缺失时失败
  - schema_version 不匹配时失败
  - 文件名引用检查（引用的文件缺失时失败）
"""
import hashlib
import json

import pytest

from app.manifest import (
    MANIFEST_FILENAME,
    SCHEMA_VERSION,
    ManifestError,
    build_manifest,
    compute_sha256,
    validate_manifest,
)


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _make_bank(tmp_path, questions=b'[{"id": "Q1"}]', dimensions=b'{}'):
    """构造一个带合法 manifest 的题库版本目录。"""
    q = tmp_path / "questions.json"
    d = tmp_path / "dimensions.json"
    q.write_bytes(questions)
    d.write_bytes(dimensions)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "bank_version": tmp_path.name,
        "questions_file": "questions.json",
        "dimensions_file": "dimensions.json",
        "questions_sha256": _sha256_text(questions.decode()),
        "dimensions_sha256": _sha256_text(dimensions.decode()),
    }
    (tmp_path / MANIFEST_FILENAME).write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    return tmp_path


def test_compute_sha256_matches_known_value(tmp_path):
    """compute_sha256 与 hashlib 直接计算一致（确定性）。"""
    p = tmp_path / "f.txt"
    p.write_text("hello", encoding="utf-8")
    assert compute_sha256(str(p)) == _sha256_text("hello")


def test_valid_manifest_passes(tmp_path):
    """正常 manifest 校验通过，返回 manifest 内容。"""
    bank = _make_bank(tmp_path)
    result = validate_manifest(str(bank))
    assert result["bank_version"] == tmp_path.name
    assert result["schema_version"] == SCHEMA_VERSION


def test_questions_hash_mismatch_fails(tmp_path):
    """修改 questions.json 后 hash 校验失败。"""
    bank = _make_bank(tmp_path)
    (bank / "questions.json").write_bytes(b'[{"id": "Q2", "changed": true}]')
    with pytest.raises(ManifestError) as exc:
        validate_manifest(str(bank))
    assert "questions.json" in str(exc.value)
    assert "不一致" in str(exc.value)


def test_dimensions_hash_mismatch_fails(tmp_path):
    """修改 dimensions.json 后 hash 校验失败。"""
    bank = _make_bank(tmp_path)
    (bank / "dimensions.json").write_bytes(b'{"new_dim": {"name": "x"}}')
    with pytest.raises(ManifestError) as exc:
        validate_manifest(str(bank))
    assert "dimensions.json" in str(exc.value)
    assert "不一致" in str(exc.value)


def test_missing_manifest_fails(tmp_path):
    """manifest 缺失时失败，报错含修复建议。"""
    (tmp_path / "questions.json").write_bytes(b"[]")
    (tmp_path / "dimensions.json").write_bytes(b"{}")
    with pytest.raises(ManifestError) as exc:
        validate_manifest(str(tmp_path))
    assert "manifest" in str(exc.value)
    assert "修复建议" in str(exc.value)


def test_schema_version_mismatch_fails(tmp_path):
    """schema_version 不匹配时失败。"""
    bank = _make_bank(tmp_path)
    manifest_path = bank / MANIFEST_FILENAME
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = "999"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ManifestError) as exc:
        validate_manifest(str(bank))
    assert "schema_version" in str(exc.value)


def test_referenced_questions_file_missing_fails(tmp_path):
    """manifest 引用的 questions_file 不存在时失败（文件名引用检查）。"""
    bank = _make_bank(tmp_path)
    (bank / "questions.json").unlink()
    with pytest.raises(ManifestError) as exc:
        validate_manifest(str(bank))
    assert "questions.json" in str(exc.value)


def test_build_manifest_computes_hashes(tmp_path):
    """build_manifest 组装 manifest 并计算两文件 sha256（与 validate_manifest 闭环）。"""
    bank = _make_bank(tmp_path)
    manifest = build_manifest(str(bank))
    assert manifest["schema_version"] == SCHEMA_VERSION
    assert manifest["bank_version"] == tmp_path.name
    assert manifest["questions_file"] == "questions.json"
    assert manifest["dimensions_file"] == "dimensions.json"
    assert manifest["questions_sha256"] == compute_sha256(str(bank / "questions.json"))
    assert manifest["dimensions_sha256"] == compute_sha256(str(bank / "dimensions.json"))
    # build_manifest 产出的 manifest 应能通过 validate_manifest
    (bank / MANIFEST_FILENAME).write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    validate_manifest(str(bank))


def test_build_manifest_raises_when_file_missing(tmp_path):
    """build_manifest 在缺少 questions.json / dimensions.json 时抛错。"""
    with pytest.raises(FileNotFoundError):
        build_manifest(str(tmp_path))


def _make_version_dir(tmp_path):
    """构造含合法 questions.index.json、但 manifest 损坏/缺失的版本目录。"""
    (tmp_path / "questions.index.json").write_text(
        json.dumps({"version": 1, "groups": []}), encoding="utf-8"
    )
    (tmp_path / "questions.json").write_bytes(b"[]")
    (tmp_path / "dimensions.json").write_bytes(b"{}")
    return tmp_path


def test_production_load_bucket_bank_rejects_bad_manifest(tmp_path, monkeypatch):
    """生产环境加载版本目录题库前强制校验 manifest，校验失败拒绝加载。"""
    import app.question_bank as qb

    bank = _make_version_dir(tmp_path)
    # 损坏的 manifest（schema_version 不匹配）
    (bank / MANIFEST_FILENAME).write_text(
        json.dumps({"schema_version": "999"}), encoding="utf-8"
    )
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("QUESTION_BANK_PATH", raising=False)
    monkeypatch.setattr(qb, "resolve_bank_dir", lambda: str(bank))
    with pytest.raises(ManifestError):
        qb.load_bucket_bank()


def test_development_load_bucket_bank_skips_manifest(tmp_path, monkeypatch):
    """开发环境加载版本目录题库时不强制 manifest（保留回退/便利）。"""
    import app.question_bank as qb

    bank = _make_version_dir(tmp_path)  # 无 manifest 文件
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("QUESTION_BANK_PATH", raising=False)
    monkeypatch.setattr(qb, "resolve_bank_dir", lambda: str(bank))
    loaded = qb.load_bucket_bank()
    assert loaded.total_questions() == 0
