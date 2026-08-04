"""
题库加载与校验模块。

规则来源: docs/DataValidation.md, docs/QuestionBankSchema.md,
          question-bank/question_bank_readme.md
"""

from __future__ import annotations

import json
import logging
import os
import warnings
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .dimensions import DIMENSION_IDS, VALID_STATUS, VALID_DIFFICULTY

logger = logging.getLogger("question_bank")

# ---------------------------------------------------------------------------
# 题库版本与路径解析
# ---------------------------------------------------------------------------
# 题库按版本文件夹管理（question-bank/v1/、v2/ …），每个版本内含：
#   questions/          分桶源文件（每桶 N 题）
#   questions.json      合并后的完整题库（后端历史数据源）
#   questions.index.json 分桶索引（结构记录：各组题数 / 桶数 / 每桶数量 / 文件位置）
# 抽题（selection）现在依赖分桶索引 questions.index.json，按需加载桶文件，
# 不再全量加载 questions.json。
#
# 版本由环境变量 QUESTION_BANK_VERSION 控制，默认 v1（docker-compose / Dockerfile 中可覆盖）。
DEFAULT_BANK_VERSION = os.environ.get("QUESTION_BANK_VERSION", "").strip() or "v1"


def resolve_bank_dir() -> str:
    """返回题库版本目录：<repo>/question-bank/<QUESTION_BANK_VERSION>。"""
    version = os.environ.get("QUESTION_BANK_VERSION", "").strip() or DEFAULT_BANK_VERSION
    return os.path.join(
        os.path.dirname(__file__), "..", "..", "question-bank", version
    )


def load_bank_index() -> dict:
    """加载当前题库版本的 questions.index.json（分桶索引）。

    索引是抽题（selection）的主数据源：记录各组题数、桶数、每桶数量与文件位置。
    生产环境下索引缺失直接抛错；开发环境回退到从 questions.json 构建虚拟索引。
    """
    bank_dir = resolve_bank_dir()
    index_path = os.path.join(bank_dir, "questions.index.json")
    if os.path.isfile(index_path):
        with open(index_path, "r", encoding="utf-8") as f:
            return json.load(f)
    # 开发回退：索引缺失时尝试用合并题库 questions.json 构建内存索引
    full_path = os.path.join(bank_dir, "questions.json")
    if os.path.isfile(full_path):
        logger.warning("未找到分桶索引 %s，回退为从 %s 构建虚拟索引", index_path, full_path)
        with open(full_path, "r", encoding="utf-8") as f:
            raw_list = json.load(f)
        return build_virtual_index(raw_list)
    if _is_production():
        raise FileNotFoundError(
            f"[production] 分桶索引不存在: {index_path}（请检查题库版本目录）"
        )
    raise FileNotFoundError(f"未找到题库索引文件: {index_path}")


def build_virtual_index(raw_list: List[dict], bucket_size: int = 4) -> dict:
    """从全量题库列表构建虚拟分桶索引（无 index 文件时的开发/测试回退）。

    按主维度（weights[0].dimension）分组，组内按 bucket_size 分桶；
    桶的 path 用 __mem__/<dim>/<idx> 伪路径，由 BucketBank.load_bucket 从内存返回。
    """
    from collections import OrderedDict

    groups: "OrderedDict[str, List[dict]]" = OrderedDict()
    for raw in raw_list:
        if not raw.get("weights"):
            continue
        primary = raw["weights"][0].get("dimension", "unknown")
        groups.setdefault(primary, []).append(raw)

    index_groups = []
    for dim, raws in groups.items():
        raws.sort(key=lambda r: r.get("id", ""))
        files = []
        for i in range(0, len(raws), bucket_size):
            files.append({
                "path": f"__mem__/{dim}/{i // bucket_size}",
                "bucket": i // bucket_size + 1,
                "questions": len(raws[i:i + bucket_size]),
            })
        index_groups.append({
            "name": dim,
            "type": "dimension",
            "bucket_size": bucket_size,
            "bucket_count": len(files),
            "question_count": len(raws),
            "files": files,
        })
    return {
        "version": 1,
        "description": "虚拟分桶索引（由全量题库构建，开发/测试回退用）",
        "total_questions": len(raw_list),
        "groups": index_groups,
    }

# [DEPRECATED] 旧的全量题库加载路径（QuestionBank / load_question_bank 专用）。
# 抽题主数据源已改为分桶索引 questions.index.json（BucketBank / load_bucket_bank），
# 正常运行时（前后端）不再加载 questions.json。保留仅为兼容：
#   - scripts/validate_bank.py 全量校验、tests/test_question_bank.py；
#   - load_bucket_bank 在分桶索引缺失时的开发回退。
# 读取优先级（仅旧接口 load_question_bank 使用）：
#   1. 显式传入的 path / 环境变量 QUESTION_BANK_PATH（自定义来源）
#   2. 生产题库：<repo>/question-bank/<version>/questions.json（version 由
#      QUESTION_BANK_VERSION 控制，默认 v1）
#   3. 开发回退：backend/app/data/questions.json（内置样例子集）
#
# 生产/开发判定：环境变量 APP_ENV=production|prod 视为生产环境。
#   - 生产环境禁止静默回退：正式题库缺失时直接抛错，绝不加载开发样例；
#   - 开发环境（默认）允许回退到内置样例题库。
PRODUCTION_BANK_PATH = os.path.join(resolve_bank_dir(), "questions.json")
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
    version = metadata.get("version")
    if not isinstance(version, int) or version < 1:
        errors.append(f"[{qid}] metadata.version 必须为正整数")
    if metadata.get("status") not in VALID_STATUS:
        errors.append(f"[{qid}] metadata.status 非法: {metadata.get('status')}")

    return errors


def load_question_bank(path: Optional[str] = None) -> "QuestionBank":
    """[DEPRECATED] 全量加载合并题库 questions.json 的旧接口（@deprecated）。

    已被 load_bucket_bank()（基于分桶索引懒加载）取代，正常运行时不再使用。
    保留兼容：scripts/validate_bank.py 全量校验、tests/test_question_bank.py、
    以及无 index 时的开发回退。新代码请改用 load_bucket_bank()。
    """
    warnings.warn(
        "load_question_bank 已弃用（@deprecated），请改用 load_bucket_bank()",
        DeprecationWarning,
        stacklevel=2,
    )
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


def _to_question(raw: dict) -> Optional[Question]:
    """把单条原始题目转换为 Question 对象；字段非法时返回 None。"""
    if not raw.get("weights"):
        return None
    try:
        return Question(
            id=raw["id"],
            content=raw["content"],
            type=raw["type"],
            category=raw.get("category", ""),
            difficulty=raw.get("difficulty", ""),
            tags=raw.get("tags", []),
            weights=[Weight(**w) for w in raw["weights"]],
            metadata=raw.get("metadata", {}),
        )
    except (KeyError, TypeError):
        return None


class QuestionBank:
    """[DEPRECATED] 全量加载的题库对象（@deprecated）。

    已被 BucketBank（基于分桶索引懒加载）取代。仅用于旧接口 load_question_bank、
    全量校验与测试兼容。新代码请使用 BucketBank。
    """

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
            q = _to_question(raw)
            if q is None:
                invalid.append(f"[{raw.get('id')}] 题目结构无法解析")
                continue
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


def load_bucket_bank(path: Optional[str] = None) -> "BucketBank":
    """加载 BucketBank（抽题主数据源），按以下优先级：

    1. 显式传入 path / 环境变量 QUESTION_BANK_PATH（自定义/测试题库文件，
       从合并题库构建虚拟索引）；
    2. 正式路径：题库版本目录 question-bank/<QUESTION_BANK_VERSION>/
       的 questions.index.json（分桶索引，懒加载桶文件）；
    3. 版本目录的 questions.json（开发回退，构建虚拟索引）。

    生产环境（APP_ENV=production|prod）下版本索引缺失直接抛错，禁止静默回退。
    """
    custom = path or os.environ.get("QUESTION_BANK_PATH", "")
    if custom and os.path.isfile(custom):
        logger.info("Loaded bucket bank from custom file: %s", custom)
        with open(custom, "r", encoding="utf-8") as f:
            return BucketBank.from_questions(json.load(f))

    bank_dir = resolve_bank_dir()
    index_path = os.path.join(bank_dir, "questions.index.json")
    if os.path.isfile(index_path):
        logger.info("Loaded bank index: %s", index_path)
        return BucketBank.from_index_file(index_path)
    # [DEPRECATED] 开发回退：索引缺失时从合并题库 questions.json 构建虚拟索引
    # （questions.json 已标记 @deprecated，仅作兼容/开发便利；生产环境不会走到这里）
    full_path = os.path.join(bank_dir, "questions.json")
    if os.path.isfile(full_path):
        logger.warning("未找到分桶索引 %s，回退为从 %s 构建虚拟索引", index_path, full_path)
        with open(full_path, "r", encoding="utf-8") as f:
            return BucketBank.from_questions(json.load(f))
    if _is_production():
        raise FileNotFoundError(
            f"[production] 分桶索引不存在: {index_path}（请检查题库版本目录）"
        )
    raise FileNotFoundError(f"未找到题库索引文件: {index_path}")


class BucketBank:
    """基于分桶索引的题库访问（抽题主数据源）。

    与 QuestionBank（全量加载）不同，BucketBank 只加载轻量索引
    questions.index.json，并**按需懒加载**桶文件，供抽题（selection）使用，
    避免每次启动/抽题都加载全部题目。

    来源两种：
      - BucketBank.from_index_file(index_path)：生产/正式路径，从磁盘加载桶文件；
      - BucketBank.from_questions(raw_list)：开发/测试回退，从全量列表构建虚拟索引
        （桶的 path 为 __mem__/<dim>/<idx>，从内存返回）。
    """

    def __init__(self, index: dict, base_dir: str):
        self.index = index
        self.base_dir = base_dir
        self._bucket_cache: Dict[str, List[Question]] = {}
        self._group_cache: Dict[str, List[Question]] = {}
        self._mem_buckets: Dict[str, List[dict]] = {}
        self._by_id: Dict[str, Question] = {}

    # ------------------------------------------------------------------
    # 构造
    # ------------------------------------------------------------------
    @classmethod
    def from_index_file(cls, index_path: str) -> "BucketBank":
        with open(index_path, "r", encoding="utf-8") as f:
            index = json.load(f)
        return cls(index, base_dir=os.path.dirname(index_path))

    @classmethod
    def from_questions(cls, raw_list: List[dict], bucket_size: int = 4) -> "BucketBank":
        """从全量题目列表构建虚拟分桶索引（开发/测试回退，无需 index 文件）。"""
        index = build_virtual_index(raw_list, bucket_size=bucket_size)
        bank = cls(index, base_dir="")
        # 把内存桶填好，供 load_bucket 的 __mem__/ 路径读取
        for group in index["groups"]:
            for f in group["files"]:
                chunk = [
                    r for r in raw_list
                    if r.get("weights")
                    and r["weights"][0].get("dimension") == group["name"]
                ]
                chunk.sort(key=lambda r: r.get("id", ""))
                start = (int(f["bucket"]) - 1) * bucket_size
                bank._mem_buckets[f["path"]] = chunk[start:start + bucket_size]
        return bank

    # ------------------------------------------------------------------
    # 索引访问
    # ------------------------------------------------------------------
    def groups(self) -> List[dict]:
        return list(self.index.get("groups", []))

    def group(self, name: str) -> Optional[dict]:
        for g in self.index.get("groups", []):
            if g["name"] == name:
                return g
        return None

    def total_questions(self) -> int:
        return self.index.get("total_questions", 0)

    def version(self) -> str:
        base = os.path.basename(os.path.abspath(self.base_dir)) if self.base_dir else ""
        return base or "1"

    # ------------------------------------------------------------------
    # 桶 / 组懒加载
    # ------------------------------------------------------------------
    def load_bucket(self, rel_path: str) -> List[Question]:
        """按需加载单个桶文件（磁盘或 __mem__ 虚拟桶），带缓存。"""
        if rel_path in self._bucket_cache:
            return self._bucket_cache[rel_path]
        if rel_path.startswith("__mem__/"):
            raw_list = self._mem_buckets.get(rel_path, [])
            qs = [q for q in (_to_question(r) for r in raw_list) if q is not None]
        else:
            path = os.path.join(self.base_dir, rel_path)
            with open(path, "r", encoding="utf-8") as f:
                raw_list = json.load(f)
            qs = [q for q in (_to_question(r) for r in raw_list) if q is not None]
        self._bucket_cache[rel_path] = qs
        for q in qs:
            self._by_id[q.id] = q
        return qs

    def questions_in_group(self, name: str) -> List[Question]:
        """加载某组全部桶的题目（懒加载 + 缓存）。"""
        if name in self._group_cache:
            return self._group_cache[name]
        group = self.group(name)
        qs: List[Question] = []
        if group:
            for f in group["files"]:
                qs.extend(self.load_bucket(f["path"]))
        self._group_cache[name] = qs
        return qs

    def get(self, question_id: str) -> Optional[Question]:
        """按 id 取题；未加载时懒加载各组直到命中。"""
        if question_id in self._by_id:
            return self._by_id[question_id]
        for g in self.groups():
            self.questions_in_group(g["name"])
            if question_id in self._by_id:
                return self._by_id[question_id]
        return None

    def active_questions(self) -> List[Question]:
        """全量加载所有组题目（统计用，注意会加载全部桶）。"""
        qs: List[Question] = []
        for g in self.groups():
            qs.extend(self.questions_in_group(g["name"]))
        return qs
