"""
十个核心价值维度的静态元数据。

来源: docs/DimensionSystem.md
"""

from typing import Dict, List, Tuple

# 维度 ID 必须与 question-bank/questions.json 中 weights[].dimension 保持一致
DIMENSIONS: Dict[str, Dict] = {
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

DIMENSION_IDS: List[str] = list(DIMENSIONS.keys())

# 结果解读中用于"矛盾分析"的典型高分冲突组合 (docs/ResultInterpretation.md 举例)
CONFLICT_PAIRS: List[Tuple[str, str]] = [
    ("freedom", "security"),
    ("altruism", "self_protection"),
    ("rule_orientation", "pragmatism"),
    ("collectivism", "freedom"),
    ("wealth", "altruism"),
    ("long_term", "pragmatism"),
    ("collectivism", "self_protection"),
]

CATEGORIES: List[str] = [
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
