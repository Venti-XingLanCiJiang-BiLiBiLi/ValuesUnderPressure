# 结果解释模型

## 1. 基本原则

结果展示价值倾向，不进行道德评价或人格定性。

避免：

> 你是自私的人

推荐：

> 在资源冲突场景中，你更倾向优先保护个人权益。

## 2. 结果组成

```json
{
  "session_id": "xxx",
  "completed": true,
  "answered_count": 50,
  "total": 50,
  "dimensions": {
    "privacy": {
      "dimension": "privacy",
      "name": "隐私保护",
      "score": 82,
      "tendency": "隐私保护",
      "description": "...",
      "consistency": 0.83,
      "question_count": 5,
      "confidence": 0.8
    },
    "altruism": {
      "dimension": "altruism",
      "name": "利他倾向",
      "score": 61,
      "tendency": "利他优先",
      "description": "...",
      "consistency": 0.9,
      "question_count": 5,
      "confidence": 0.86
    }
  },
  "confidence": 0.86,
  "conflicts": [],
  "uncertain_dimensions": []
}
```

每个维度包含：

- 当前分数（`score`，0~100）
- 倾向方向（`tendency`）
- 典型行为描述（`description`）
- 作答一致性（`consistency`，0~1，样本不足为 `null`）
- 维度级置信度（`confidence`，0~1，综合题量 / 一致性 / 权重覆盖）

## 3. 维度解释

每个维度包含：

- 当前分数
- 倾向方向
- 典型行为描述
- 可能冲突维度

## 4. 矛盾分析

同时展示高分冲突组合，例如：

- 高自由 + 高安全
- 高利他 + 高自我保护
- 高规则 + 高结果主义

说明用户可能存在复杂价值平衡，而非简单分类。

## 5. 不确定性

若同维度问题回答高度矛盾：

输出：

> 该价值维度存在较强情境依赖。

而不是强行归类。
