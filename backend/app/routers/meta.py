"""基础元数据路由：健康检查、维度元数据与隐私政策。"""
from __future__ import annotations

from fastapi import APIRouter, Request

from .. import db
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


# 隐私政策（结构化正文；保留期在接口内按运行期配置填充，保证与部署一致）。
# 前端 views/PrivacyView.vue 的内置回退文案需与本处保持同步（双源同步）。
PRIVACY_POLICY_VERSION = "1.0"
PRIVACY_EFFECTIVE_DATE = "2026-08-04"


@router.get("/api/meta/privacy")
@limiter.limit("120/minute")
def privacy_policy(request: Request):
    """返回隐私政策（结构化正文 + 实际保留期）。

    保留期取自运行期环境变量（SESSION_TTL_DAYS / COMPLETED_SESSION_TTL_DAYS），
    保证政策文案与部署配置始终一致；前端拉取失败时回退到内置文案。
    """
    session_ttl = db.SESSION_TTL_DAYS
    completed_ttl = db.COMPLETED_SESSION_TTL_DAYS
    return {
        "version": PRIVACY_POLICY_VERSION,
        "effective_date": PRIVACY_EFFECTIVE_DATE,
        "retention": {
            "session_ttl_days": session_ttl,
            "completed_session_ttl_days": completed_ttl,
        },
        "sections": [
            {
                "title": "概述",
                "body": (
                    "本应用（取舍之间 · Values Under Pressure）致力于最小化数据收集。"
                    "你无需注册或登录即可使用测试功能。"
                ),
            },
            {
                "title": "我们收集什么",
                "body": (
                    "使用测试功能时，服务端会保存：\n"
                    "- 你对每道题的答案（是/否）与作答耗时；\n"
                    "- 答案的修改记录（修改前/后的答案）；\n"
                    "- 测试结果（10 个价值维度的分数、一致性、置信度）；\n"
                    "- 随机会话标识（仅用于把同一测试的数据关联起来）。"
                ),
            },
            {
                "title": "我们不收集什么",
                "body": (
                    "我们不收集姓名、邮箱、手机号等个人身份信息；"
                    "不使用 Cookie 进行追踪；不投放广告。"
                ),
            },
            {
                "title": "服务端数据保留",
                "body": (
                    f"服务端数据保存在 SQLite 数据库中，并按期自动删除：\n"
                    f"- 进行中的测试会话默认保留 {session_ttl} 天；\n"
                    f"- 已完成的测试结果默认保留 {completed_ttl} 天。\n"
                    "到期后，相关答案、结果与修改记录会被后台任务一并删除。"
                ),
            },
            {
                "title": "数据用途",
                "body": (
                    "收集的数据仅用于：生成本次测试结果，以及以匿名统计形式改进"
                    "测试质量（如题目区分度、完成率）。我们不会用这些数据识别你的"
                    "个人身份。"
                ),
            },
            {
                "title": "数据共享",
                "body": "我们不会向任何第三方出售、出租或共享你的测试数据。",
            },
            {
                "title": "客户端本地存储",
                "body": (
                    "结果存档保存在你的浏览器本地存储（localStorage）中，最多保留"
                    " 50 条，仅存本机、不上传服务器；答题进度临时保存在会话存储"
                    "（sessionStorage）中，24 小时后或关闭标签页后自动清除。"
                ),
            },
            {
                "title": "限流与安全",
                "body": (
                    "为防滥用，服务端会基于 IP 做请求频率限制；该信息仅存于内存，"
                    "不持久化，也不用于识别身份。"
                ),
            },
            {
                "title": "你的权利",
                "body": (
                    "你可以随时在首页删除本地存档。服务端数据到期后会自动删除，"
                    "无需额外操作。"
                ),
            },
            {
                "title": "政策变更与联系方式",
                "body": (
                    "本政策如发生变更，我们会更新版本号与生效日期。如有疑问或需要"
                    "删除数据，可通过项目仓库联系："
                    "https://github.com/Venti-XingLanCiJiang-BiLiBiLi/ValuesUnderPressure"
                ),
            },
        ],
    }
