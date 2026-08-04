"""API 限流与防滥用（#9）。

基于 slowapi（内存存储），按客户端真实 IP 限流。

反代说明：部署为 Nginx 反代 `/api` 到后端，Nginx 已注入 `X-Real-IP`
（真实客户端 IP）。slowapi 默认的 `get_remote_address` 取的是
`request.client.host`，在反代下会统一为 Nginx 容器 IP，导致所有用户
共用一个限流桶；故这里优先信任 `X-Real-IP`，回退 `X-Forwarded-For`
首项，再回退直连地址。

单 worker uvicorn 部署下内存存储有效；未来若扩展多实例，可平滑切换
为 Redis 存储（limits 支持）。
"""
from __future__ import annotations

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request


def client_ip(request: Request) -> str:
    """取客户端真实 IP（用于限流桶键）。

    优先 `X-Real-IP`（Nginx 注入），回退 `X-Forwarded-For` 首项，
    再回退直连地址 `client.host`。
    """
    real = request.headers.get("X-Real-IP")
    if real:
        return real.strip()
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=client_ip)

__all__ = ["RateLimitExceeded", "_rate_limit_exceeded_handler", "limiter"]
