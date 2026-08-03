"""
题库加载与校验模块。

规则来源: docs/DataValidation.md, docs/QuestionBankSchema.md,
          question-bank/question_bank_readme.md
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .dimensions import DIMENSION_IDS, VALID_STATUS, VALID_DIFFICULTY

logger = logging.getLogger("question_bank")

# 后端优先读取仓库正式题库 question-bank/questions.json（500 题），题库与代码分离。
# 若正式题库不存在（例如本地/测试环境），则回退到内置样例题库
# backend/app/data/questions.json，保证服务在没有完整题库文件时依然可以启动。
#
# 读取优先级：
#   1. 显式传入的 path / 环境变量 QUESTION_BANK_PATH（自定义来源）
#   2. 生产题库：<repo>/question-bank/questions.json
#   3. 开发回退：backend/app/data/questions.json（内置样例子集）
#
# 生产/开发判定：环境变量 APP_ENV=production|prod 视为生产环境。
#   - 生产环境禁止静默回退：正式题库缺失时直接抛错，绝不加载开发样例；
#   - 开发环境（默认）允许回退到内置样例题库。
PRODUCTION_BANK_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "question-bank", "questions.json"
)
FALLBACK_BANK_PATH = os.path.join(os.path.dirname(__file__), "data", "questions.json")


def _is_production() -> bool:
    return os.environ.get("APP_ENV", "").strip().lower() in ("production", "prod")


def _candidates(path: Optional[str]) -> List[tuple]:
    """返回 [(kind, path), ...]，kind ∈ {custom, production, fallback}。

    生产环境下不列入开发回退候选，避免静默 fallback。
    """
    candidates: List[tuple] = []
    if path:
        candidates.append(("custom", path))
    env_path = os.environ.get("QUESTION_BANK_PATH", "")
    if env_path:
        candidates.append(("custom", env_path))
    candidates.append(("production", PRODUCTION_BANK_PATH))
    if not _is_production():
        candidates.append(("fallback", FALLBACK_BANK_PATH))
    return candidates


@dataclass
class Weight:
    dimension: str
    yes: int
    no: int


@dataclass
class Question:
    id: str
    content: str
    type: str
    category: str
    difficulty: str
    tags: List[str]
    weights: List[Weight]
    metadata: Dict = field(default_factory=dict)

    @property
    def status(self) -> str:
        return self.metadata.get("status", "draft")

    @property
    def dimensions(self) -> List[str]:
        return [w.dimension for w in self.weights]


class ValidationError(Exception):
    pass


def _validate_raw(raw: dict, seen_ids: set) -> List[str]:
    """对单条原始题目做 schema/权重/内容层面的校验，返回问题列表（不抛异常）。"""
    errors = []
    qid = raw.get("id")
    if not qid:
        errors.append("缺少 id")
    elif qid in seen_ids:
        errors.append(f"id 重复: {qid}")

    if not raw.get("content"):
        errors.append(f"[{qid}] content 不能为空")

    if raw.get("type") != "YN":
        errors.append(f"[{qid}] type 必须为 YN")

    if raw.get("difficulty") not in VALID_DIFFICULTY:
        errors.append(f"[{qid}] difficulty 非法: {raw.get('difficulty')}")

    weights = raw.get("weights") or []
    if not weights:
        errors.append(f"[{qid}] weights 至少包含一个维度")

    seen_dims = set()
    for w in weights:
        dim = w.get("dimension")
        yes, no = w.get("yes"), w.get("no")
        if dim not in DIMENSION_IDS:
            errors.append(f"[{qid}] 未知维度: {dim}")
        if dim in seen_dims:
            errors.append(f"[{qid}] 维度重复: {dim}")
        seen_dims.add(dim)
        for val, name in ((yes, "yes"), (no, "no")):
            if not isinstance(val, int) or not (-5 <= val <= 5):
                errors.append(f"[{qid}] 权重 {name} 超出 -5~5 范围: {val}")
        if yes == 0 and no == 0:
            errors.append(f"[{qid}] yes 和 no 不能同时为 0")

    metadata = raw.get("metadata") or {}
    if not isinstance(metadata.get("version"), int) or metadata.get("version") < 1:
        errors.append(f"[{qid}] metadata.version 必须为正整数")
    if metadata.get("status") not in VALID_STATUS:
        errors.append(f"[{qid}] metadata.status 非法: {metadata.get('status')}")

    return errors


def load_question_bank(path: Optional[str] = None) -> "QuestionBank":
    for kind, candidate in _candidates(path):
        if not candidate or not os.path.isfile(candidate):
            # 生产环境下不存在的题库来源必须显式报错，禁止静默回退
            # （回退候选在生产模式下根本不会被列入）。
            if _is_production():
                raise FileNotFoundError(
                    f"[production] 题库文件不存在，禁止回退开发样例: "
                    f"{candidate or '(未设置 QUESTION_BANK_PATH)'}"
                )
            continue
        with open(candidate, "r", encoding="utf-8") as f:
            raw_list = json.load(f)
        if kind == "production":
            logger.info(
                "Loaded production question bank: %s (%d 题)", candidate, len(raw_list)
            )
        elif kind == "fallback":
            logger.info(
                "Loaded development fallback question bank: %s (%d 题)",
                candidate,
                len(raw_list),
            )
        else:
            logger.info("Loaded question bank (custom): %s (%d 题)", candidate, len(raw_list))
        return QuestionBank.from_raw(raw_list, source=candidate)
    raise FileNotFoundError(
        "未找到题库文件，请设置环境变量 QUESTION_BANK_PATH 指向 "
        "question-bank/questions.json"
    )


class QuestionBank:
    def __init__(self, questions: List[Question], invalid: List[str], source: str):
        self.questions = questions
        self.invalid = invalid  # 校验失败被剔除的原因列表（仅记录，不阻断启动）
        self.source = source
        self.by_id: Dict[str, Question] = {q.id: q for q in questions}

    @classmethod
    def from_raw(cls, raw_list: List[dict], source: str) -> "QuestionBank":
        questions: List[Question] = []
        invalid: List[str] = []
        seen_ids = set()
        for raw in raw_list:
            errors = _validate_raw(raw, seen_ids)
            if errors:
                invalid.extend(errors)
                # id 唯一性冲突之外的问题，仍然按"跳过该题"处理，不让单题错误拖垮整个题库
                continue
            seen_ids.add(raw["id"])
            q = Question(
                id=raw["id"],
                content=raw["content"],
                type=raw["type"],
                category=raw.get("category", ""),
                difficulty=raw["difficulty"],
                tags=raw.get("tags", []),
                weights=[Weight(**w) for w in raw["weights"]],
                metadata=raw.get("metadata", {}),
            )
            questions.append(q)
        if invalid:
            for err in invalid:
                logger.warning("题库校验失败并已跳过: %s", err)
        return cls(questions, invalid, source)

    def active_questions(self) -> List[Question]:
        return [q for q in self.questions if q.status in ("active", "experimental")]

    def by_dimension(self, dimension: str, exclude_ids: Optional[set] = None) -> List[Question]:
        exclude_ids = exclude_ids or set()
        return [
            q
            for q in self.active_questions()
            if dimension in q.dimensions and q.id not in exclude_ids
        ]

    def by_category(self, category: str) -> List[Question]:
        return [q for q in self.active_questions() if q.category == category]

    def get(self, question_id: str) -> Optional[Question]:
        return self.by_id.get(question_id)

    def version(self) -> str:
        versions = {q.metadata.get("version", 1) for q in self.questions}
        return str(max(versions)) if versions else "1"
