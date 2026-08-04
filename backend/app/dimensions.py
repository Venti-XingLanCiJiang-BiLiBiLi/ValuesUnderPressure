"""
十个核心价值维度的元数据。

来源: docs/DimensionSystem.md

**数据源（单一数据源）**：维度元数据（英文 ID → 中文 name/description/direction/
high/low 等）存放在题库版本目录 `question-bank/<QUESTION_BANK_VERSION>/dimensions.json`，
与题目同版本管理、随题库统一调用。本模块启动时从该文件加载 `DIMENSIONS`；
开发/测试环境文件缺失/非法时回退到内置 `_DEFAULT_DIMENSIONS`（仅开发/测试兜底，
正式数据以题库为准）；**生产环境（APP_ENV=production|prod）dimensions.json 缺失
或损坏（JSON 非法/结构不符）时禁止回退并直接抛错**，避免题库版本与维度定义不匹配。
`reload_dimensions()` 可在运行时重载（配合题库热更新 #14），保持「题库 + 维度元数据」
同源一致。

逻辑常量（与展示无关）保留在本模块：
  CONFLICT_PAIRS / CATEGORIES / VALID_STATUS / VALID_DIFFICULTY
"""

from __future__ import annotations

import json
import logging
import os

from .bank_paths import is_production, resolve_bank_dir

logger = logging.getLogger("dimensions")

# ---------------------------------------------------------------------------
# 内置默认维度元数据（开发/测试兜底）
# 正式数据以题库 question-bank/<version>/dimensions.json 为准；本字典仅用于题库
# 文件缺失时的降级，避免 import 时因找不到题库而崩溃。
# ---------------------------------------------------------------------------
_DEFAULT_DIMENSIONS: dict[str, dict] = {
    "self_protection": {
        "name": "自我保护",
        "description": "优先保护自身利益、资源和安全的倾向",
        "direction": ["利他优先", "自我保护优先"],
        "high": "在资源与风险冲突的场景中，你更倾向优先保护自己的利益、时间与安全。",
        "low": "在资源与风险冲突的场景中，你更倾向优先考虑他人或集体，即使这会让自己承担更多成本。",
    },
    "altruism": {
        "name": "利他倾向",
        "description": "为他人或整体利益牺牲自身资源的倾向",
        "direction": ["自我优先", "利他优先"],
        "high": "你更愿意为他人或集体牺牲自己的时间、金钱甚至安全。",
        "low": "在利益冲突时，你更倾向优先保障自己的处境，而非主动为他人让渡资源。",
    },
    "freedom": {
        "name": "自由需求",
        "description": "对自主权、选择权的重视程度",
        "direction": ["接受约束", "追求自主"],
        "high": "你非常看重自主选择权，倾向拒绝任何限制你独立决策的安排。",
        "low": "为了换取稳定或集体协作，你愿意接受一定程度的外部约束和统一安排。",
    },
    "security": {
        "name": "安全需求",
        "description": "对稳定、秩序和风险控制的需求",
        "direction": ["接受风险", "追求稳定"],
        "high": "你更看重生活的稳定与可预期性，倾向规避风险即使因此放弃潜在收益。",
        "low": "你能够接受较高的不确定性，愿意为自由或回报承担相应风险。",
    },
    "privacy": {
        "name": "隐私保护",
        "description": "对个人边界和信息控制的需求",
        "direction": ["开放共享", "隐私保护"],
        "high": "你非常重视个人信息与边界，倾向拒绝任何以隐私换取便利或收益的安排。",
        "low": "你对个人信息的暴露相对宽容，愿意用部分隐私换取便利、社交或收益。",
    },
    "wealth": {
        "name": "财富偏好",
        "description": "对物质收益和资源积累的重视",
        "direction": ["非物质优先", "财富优先"],
        "high": "在权衡时，你更倾向优先考虑物质收益和财富积累。",
        "low": "相较于金钱，你更愿意为自由、关系或理想让渡财富。",
    },
    "rule_orientation": {
        "name": "规则意识",
        "description": "对制度、法律和程序正义的重视",
        "direction": ["结果优先", "规则优先"],
        "high": "你更倾向坚持规则与程序正义，即使这会带来效率损失或个人代价。",
        "low": "在规则与现实结果冲突时，你更倾向优先追求实际效果，而非严格遵守流程。",
    },
    "pragmatism": {
        "name": "现实主义",
        "description": "对现实结果和可执行性的偏好",
        "direction": ["理想/原则优先", "现实结果优先"],
        "high": "你更看重现实可行性与即时结果，愿意为此让步原则或长远理想。",
        "low": "你更愿意坚持原则或长远理想，即使短期内看不到现实回报。",
    },
    "collectivism": {
        "name": "集体主义",
        "description": "对群体利益和共同目标的重视",
        "direction": ["个人优先", "集体优先"],
        "high": "你更倾向以集体、团队或群体利益为重，愿意为此让渡个人利益。",
        "low": "你更倾向以个人利益和独立判断为重，对集体统一安排相对保留。",
    },
    "long_term": {
        "name": "长期主义",
        "description": "对未来收益和长期价值的重视",
        "direction": ["短期优先", "长期优先"],
        "high": "你更愿意为长远的目标和未来价值，忍受当下的不便或牺牲。",
        "low": "你更倾向优先满足当下的需求和体验，而非为遥远的未来做出让步。",
    },
}

# 维度元数据（对象引用保持稳定：重载时就地 clear/update，依赖方 `from .dimensions
# import DIMENSIONS` 仍能观察到更新）。
DIMENSIONS: dict[str, dict] = dict(_DEFAULT_DIMENSIONS)


def _validate_meta(raw: dict) -> None:
    """校验 dimensions.json 结构；非法时抛 ValueError。"""
    if not isinstance(raw, dict) or not raw:
        raise ValueError("dimensions.json 顶层应为非空对象")
    for dim, meta in raw.items():
        if not isinstance(meta, dict):
            raise ValueError(f"维度 {dim} 的元数据应为对象")
        for key in ("abbr", "name", "description", "direction", "high", "low"):
            if key not in meta:
                raise ValueError(f"维度 {dim} 缺少字段: {key}")
        if not (isinstance(meta["direction"], list) and len(meta["direction"]) == 2):
            raise ValueError(f"维度 {dim} 的 direction 应为长度为 2 的数组")


def _load_dimensions() -> None:
    """从当前题库版本目录的 dimensions.json 加载维度元数据，就地更新 DIMENSIONS。

    开发/测试环境：文件缺失 / JSON 非法 / 结构不符时回退内置默认，保证运行不中断。
    生产环境（APP_ENV=production|prod）：dimensions.json **缺失或损坏**时禁止回退，
    直接抛错，避免题库版本与维度定义不匹配导致测评结果错误。
    """
    global DIMENSIONS
    path = os.path.join(resolve_bank_dir(), "dimensions.json")
    if not os.path.isfile(path) and is_production():
        bank_version = os.path.basename(os.path.normpath(resolve_bank_dir()))
        raise FileNotFoundError(
            f"[production] 维度元数据文件缺失，禁止回退内置默认: {path}\n"
            f"当前题库版本: {bank_version}\n"
            "修复建议: 确保该版本目录存在 dimensions.json，且与 questions.json 属于同一"
            "题库版本；可运行 python scripts/generate_manifest.py 生成 manifest.json 并校验一致性。"
        )
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        _validate_meta(raw)
        DIMENSIONS.clear()
        DIMENSIONS.update(raw)
        logger.info("已从题库加载维度元数据: %s（%d 个维度）", path, len(raw))
    except Exception as e:  # noqa: BLE001
        if is_production():
            # 生产环境：文件存在但 JSON 非法 / 结构不符同样禁止回退，直接抛错
            bank_version = os.path.basename(os.path.normpath(resolve_bank_dir()))
            raise RuntimeError(
                f"[production] 维度元数据文件损坏，禁止回退内置默认: {path}: {e}\n"
                f"当前题库版本: {bank_version}\n"
                "修复建议: 修复 dimensions.json 的 JSON/结构，或恢复与题库同版本的 "
                "dimensions.json 后重新生成 manifest（scripts/generate_manifest.py）。"
            ) from e
        logger.warning("加载题库维度元数据失败，回退内置默认: %s", e)
        DIMENSIONS.clear()
        DIMENSIONS.update(_DEFAULT_DIMENSIONS)


_load_dimensions()

DIMENSION_IDS: list[str] = list(DIMENSIONS.keys())

# 结果解读中用于"矛盾分析"的典型高分冲突组合 (docs/ResultInterpretation.md 举例)
CONFLICT_PAIRS: list[tuple[str, str]] = [
    ("freedom", "security"),
    ("altruism", "self_protection"),
    ("rule_orientation", "pragmatism"),
    ("collectivism", "freedom"),
    ("wealth", "altruism"),
    ("long_term", "pragmatism"),
    ("collectivism", "self_protection"),
]

CATEGORIES: list[str] = [
    "personal_boundary",
    "privacy",
    "freedom",
    "safety",
    "wealth",
    "morality",
    "social",
    "future",
    "risk",
    "control",
    "must",
    "experimental",
]

VALID_STATUS = {"draft", "active", "experimental", "deprecated"}
VALID_DIFFICULTY = {"easy", "medium", "hard"}


def reload_dimensions() -> dict[str, dict]:
    """运行时重新加载维度元数据（配合题库热更新 #14）。

    就地更新 DIMENSIONS / DIMENSION_IDS，保持对象引用稳定，让已导入的模块立即生效。
    """
    global DIMENSIONS
    _load_dimensions()
    DIMENSION_IDS.clear()
    DIMENSION_IDS.extend(list(DIMENSIONS.keys()))
    return DIMENSIONS
