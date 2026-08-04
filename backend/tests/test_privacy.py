"""meta 路由：隐私政策接口测试。

覆盖点：
  - /api/meta/privacy 返回结构化字段（version / effective_date / retention / sections）；
  - 保留期正文与实际配置（SESSION_TTL_DAYS / COMPLETED_SESSION_TTL_DAYS）一致；
  - 章节标题唯一。
"""
from __future__ import annotations

from starlette.requests import Request

from app.routers.meta import privacy_policy


def _req() -> Request:
    """构造最小 mock Request，供被 slowapi 装饰的路由函数直接调用。"""
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": [],
            "query_string": b"",
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )


def test_privacy_policy_shape():
    data = privacy_policy(_req())
    assert data["version"]
    assert data["effective_date"]
    assert data["retention"]["session_ttl_days"] > 0
    assert data["retention"]["completed_session_ttl_days"] > 0
    assert data["sections"]
    for s in data["sections"]:
        assert s["title"]
        assert s["body"]


def test_privacy_retention_body_matches_config():
    data = privacy_policy(_req())
    retention_body = next(
        s["body"] for s in data["sections"] if s["title"] == "服务端数据保留"
    )
    assert str(data["retention"]["session_ttl_days"]) in retention_body
    assert str(data["retention"]["completed_session_ttl_days"]) in retention_body


def test_privacy_sections_titles_unique():
    data = privacy_policy(_req())
    titles = [s["title"] for s in data["sections"]]
    assert len(titles) == len(set(titles))
