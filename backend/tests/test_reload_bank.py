"""题库热更新接口测试 (#14)。

覆盖：
  - 正常 reload 返回新版本信息
  - 错误 token 返回 403
  - 题库损坏返回 500
"""
import os
import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException

from app.main import reload_bank


def test_reload_bank_success():
    """正常 reload 返回新版本信息。"""
    os.environ["ADMIN_TOKEN"] = "test-token-123"
    try:
        with patch("app.main.load_bucket_bank") as mock_load:
            mock_bank = MagicMock()
            mock_bank.version.return_value = "v1"
            mock_bank.groups.return_value = [{"name": "test"}]
            mock_bank.total_questions.return_value = 100
            mock_load.return_value = mock_bank
            
            result = reload_bank(x_admin_token="test-token-123")
            assert result["ok"] is True
            assert result["version"] == "v1"
            assert result["groups"] == 1
            assert result["active_questions"] == 100
    finally:
        del os.environ["ADMIN_TOKEN"]


def test_reload_bank_wrong_token():
    """错误 token 返回 403。"""
    os.environ["ADMIN_TOKEN"] = "correct-token"
    try:
        with pytest.raises(HTTPException) as exc:
            reload_bank(x_admin_token="wrong-token")
        assert exc.value.status_code == 403
    finally:
        del os.environ["ADMIN_TOKEN"]


def test_reload_bank_no_token_configured():
    """未配置 ADMIN_TOKEN 时返回 403。"""
    os.environ.pop("ADMIN_TOKEN", None)
    with pytest.raises(HTTPException) as exc:
        reload_bank(x_admin_token="any-token")
    assert exc.value.status_code == 403


def test_reload_bank_corrupted_bank():
    """题库损坏时返回 500。"""
    os.environ["ADMIN_TOKEN"] = "test-token"
    try:
        with patch("app.main.load_bucket_bank", side_effect=FileNotFoundError("题库文件缺失")):
            with pytest.raises(HTTPException) as exc:
                reload_bank(x_admin_token="test-token")
            assert exc.value.status_code == 500
            assert "Reload failed" in str(exc.value.detail)
    finally:
        del os.environ["ADMIN_TOKEN"]
