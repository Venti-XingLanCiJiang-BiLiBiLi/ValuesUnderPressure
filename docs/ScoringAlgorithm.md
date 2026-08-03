# 性格测试评分算法设计

## 1. 基本模型

用户回答每道 Y/N 题后，根据题目权重累加各维度分数。

## 2. 计算规则

回答 Y：

```
score[dimension] += weight.yes
```

回答 N：

```
score[dimension] += weight.no
```

## 3. 标准化

由于不同维度题目数量可能不同，最终需要归一化。

建议：

```
normalized = (score - min) / (max - min)
```

转换为 0-100 分。

## 4. 一致性分析

同一维度多个问题之间计算一致程度：

- 高一致：稳定价值倾向
- 低一致：价值冲突或情境依赖

## 5. 维度级置信度（confidence）

除整体 `confidence` 外，每个维度额外输出 0~1 的 `confidence`，综合三个信号：

| 信号 | 含义 | 对置信度的影响 |
| --- | --- | --- |
| 权重覆盖 `weight_coverage` | 已作答题目权重区间 / 该维度全部题目权重区间 | 覆盖不足 -> 降低 |
| 一致性 `consistency` | 作答方向稳定程度（样本不足按 0 处理） | 高度矛盾 / 样本不足 -> 降低 |
| 题量 `quantity` | `min(1, question_count / 5)` | 题目数量过少 -> 降低 |

计算公式：

```
confidence = 0.5 * weight_coverage + 0.3 * consistency + 0.2 * quantity
```

- 结果限制在 0~1；
- 维度题量 < 5 时 `quantity < 1`，confidence 自动降低；
- 该维度回答高度矛盾时 `consistency` 低，confidence 自动降低。

## 6. 输出

输出维度画像，不输出人格定性判断。

示例：

```json
{
  "privacy": {
    "score": 82,
    "confidence": 0.82
  },
  "altruism": {
    "score": 61,
    "confidence": 0.76
  },
  "freedom": {
    "score": 90,
    "confidence": 0.88
  }
}
```
