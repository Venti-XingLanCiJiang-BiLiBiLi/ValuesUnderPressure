# 性格测试价值维度体系设计

## 1. 设计原则

本测试测量的是价值冲突中的选择倾向，而非简单人格标签。

每个维度代表一个连续轴，不代表好坏。

## 2. 第一版核心维度

| ID | 名称 | 描述 |
|-|-|-|
| self_protection | 自我保护 | 优先保护自身利益、资源和安全 |
| altruism | 利他倾向 | 为他人或整体利益牺牲自身资源的倾向 |
| freedom | 自由需求 | 对自主权、选择权的重视程度 |
| security | 安全需求 | 对稳定、秩序和风险控制的需求 |
| privacy | 隐私保护 | 对个人边界和信息控制的需求 |
| wealth | 财富偏好 | 对物质收益和资源积累的重视 |
| rule_orientation | 规则意识 | 对制度、法律和程序正义的重视 |
| pragmatism | 现实主义 | 对现实结果和可执行性的偏好 |
| collectivism | 集体主义 | 对群体利益和共同目标的重视 |
| long_term | 长期主义 | 对未来收益和长期价值的重视 |

## 3. 维度数据格式

维度元数据（英文 ID → 中文 name/description/direction 等）存放在**题库版本目录**
`question-bank/<version>/dimensions.json`，与题目同版本管理，作为前后端统一的单一数据源：

- 后端启动时从该文件加载 `DIMENSIONS`（`backend/app/dimensions.py`），并通过
  `GET /api/dimensions` 提供给前端；
- 前端结果页/首页的维度中文标签均来自后端返回，不单独维护副本；
- 修改维度名称、描述或方向时，只需改 `question-bank/<version>/dimensions.json`。

```json
{
  "privacy": {
    "abbr": "PR",
    "name": "隐私保护",
    "description": "对个人边界和信息控制的需求",
    "direction": ["开放共享", "隐私保护"],
    "high": "…",
    "low": "…"
  }
}
```

## 4. 输出原则

结果应描述倾向，例如：

> 你在资源冲突场景下更倾向保护个人边界。

避免输出：

> 你是自私的人。
