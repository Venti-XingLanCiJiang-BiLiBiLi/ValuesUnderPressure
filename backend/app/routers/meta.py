"""基础元数据路由：健康检查与维度元数据。"""
from __future__ import annotations

from fastapi import APIRouter, Request

from ..bank_state import get_bank
from ..dimensions import DIMENSIONS
from ..rate_limit import limiter

router = APIRouter()


@router.get("/api/health")
@limiter.limit("100/minute")
def health(request: Request):
    bank = get_bank()
    return {
        "status": "ok",
        "question_bank_version": bank.version(),
        "groups": len(bank.groups()),
        "active_questions": bank.total_questions(),
    }


@router.get("/api/dimensions")
@limiter.limit("120/minute")
def list_dimensions(request: Request):
    return {
        dim: {
            "name": meta["name"],
            "description": meta["description"],
            "direction": meta["direction"],
        }
        for dim, meta in DIMENSIONS.items()
    }
