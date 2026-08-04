"""管理接口：题库热更新（#14）。"""
from __future__ import annotations

import logging
import os

from fastapi import APIRouter, Header, HTTPException, Request

from .. import bank_state
from ..dimensions import reload_dimensions
from ..question_bank import load_bucket_bank
from ..rate_limit import limiter

logger = logging.getLogger("apersonalitytest")

router = APIRouter()

# 保留备用：模块级缓存 ADMIN_TOKEN，供后续其它 admin 接口复用。
# 当前 reload_bank 的鉴权在函数内实时读取环境变量（便于测试动态注入）。
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")


@router.post("/api/admin/reload-bank")
@limiter.limit("10/minute")
def reload_bank(request: Request, x_admin_token: str = Header(...)):
    """热更新题库（#14）。需要 X-Admin-Token 请求头鉴权。

    注意：热更新后，已创建的活跃会话可能因题库变化而缺少题目
    （_session_questions 已过滤 None，但文档应明确此行为）。
    """
    token = os.environ.get("ADMIN_TOKEN", "")
    if not token or x_admin_token != token:
        raise HTTPException(403, "Invalid admin token")

    try:
        new_bank = load_bucket_bank()
        bank_state.set_bank(new_bank)
        # 维度元数据与题库同源存放（question-bank/<version>/dimensions.json），
        # 热更新题库时一并重载，保持「题库 + 维度」一致。
        reload_dimensions()
        logger.info(
            "题库热更新成功: version=%s groups=%d active_questions=%d",
            new_bank.version(),
            len(new_bank.groups()),
            new_bank.total_questions(),
        )
        return {
            "ok": True,
            "version": new_bank.version(),
            "groups": len(new_bank.groups()),
            "active_questions": new_bank.total_questions(),
        }
    except Exception as e:
        logger.error("题库热更新失败: %s", e)
        raise HTTPException(500, f"Reload failed: {e}")
