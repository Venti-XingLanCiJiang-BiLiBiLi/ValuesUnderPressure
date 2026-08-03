# 性格测试题库说明（question-bank）

本目录下的 `questions.json` 是 aPersonalityTest 项目的**正式题库**，供后端组卷、计分与统计使用。

- 测试机制：通过**极端价值冲突场景**中的 Y/N 二选一，测量用户在 10 个价值维度上的底线与优先级。
- 设计原则：**无绝对正确答案、不评价善恶、不测知识**，只测价值排序，允许不同情境下出现矛盾。

---

## 1. 文件与数据来源

| 文件 | 说明 |
| --- | --- |
| `questions.json` | **正式题库**（500 题，`Q00001`~`Q00500`），后端唯一数据源 |
| `drafts/` | 生成题库的中间批次源文件（**本地工作目录，不入库**，已加入 `.gitignore`） |
| `tools/build_questions.py` | 合并 + 校验脚本（**本地工具，不入库**），用于重新生成 `questions.json` |
| `questions.template.json` | 单题结构模板示例 |

> 后端请只依赖 `questions.json`。`drafts/`、`tools/` 不随仓库分发，仅用于本地维护与重新生成。

---

## 2. 题目数据结构

`questions.json` 顶层为数组，每项一道题。字段总览：

```jsonc
{
  "id": "Q00001",              // 全局唯一 ID
  "content": "你愿意……吗？",   // 题目文本（Y/N 二选一）
  "type": "YN",                // 固定 "YN"
  "category": "wealth",        // 场景分类（12 类之一）
  "difficulty": "medium",      // 难度 easy | medium | hard
  "tags": ["self_protection", "altruism"],  // 维度标签
  "weights": [                 // 多维影响权重（至少 1 条）
    { "dimension": "self_protection", "yes": 5, "no": -5 },
    { "dimension": "altruism", "yes": -3, "no": 3 }
  ],
  "metadata": { "version": 1, "status": "draft" }
}
```

---

## 3. 字段详解

### 3.1 `id`
全局唯一、连续编号：`Q00001` ~ `Q00500`。可用于随机抽样的去重与结果记录。

### 3.2 `content`
题目文本，固定为「你愿意牺牲【A】，换取【B】吗？」式的底线压力测试。**作答只允许 Y / N**。

### 3.3 `type`
恒为 `"YN"`（二选一）。后端可据此决定渲染与作答数据结构。

### 3.4 `category`（场景分类，共 12 类）

| category | 含义 |
| --- | --- |
| `personal_boundary` | 个人边界 |
| `privacy` | 隐私 |
| `freedom` | 自由 |
| `safety` | 安全 |
| `wealth` | 财富 |
| `morality` | 道德 |
| `social` | 社会/人际 |
| `future` | 未来/长远 |
| `risk` | 风险 |
| `control` | 控制/秩序 |
| `must` | 必答题（固定出现在每张试卷，用于锚定） |
| `experimental` | 实验性题目（数据试运行，正式上线可单独开关） |

### 3.5 `difficulty`
`easy` / `medium` / `hard`，按牺牲强度与抽象程度划分，供组卷时做难度配比。

### 3.6 `tags`
该题关联的维度名列表（与 `weights` 中的维度一致），用于检索与过滤。

### 3.7 `weights`（核心字段）
多维度影响权重，规则：

- 每条 = `{ "dimension", "yes", "no" }`。
- 取值：**-5 ~ +5** 的整数（强烈 ±5 / 明显 ±3 / 轻微 ±1）。
- `yes`：用户答 **Y** 时对该维度的得分贡献；`no`：答 **N** 时的贡献。
- 约束（见 `docs/DataValidation.md`）：
  - `yes` 与 `no` **不能同时为 0**；
  - 同一道题内 **同一 dimension 不能重复出现**；
  - dimension 必须是 10 个核心维度之一。

### 3.8 `metadata`
`version`：数据结构版本；`status`：当前为 `"draft"`。统计扩展见 §9。

---

## 4. 维度体系（10 个核心维度）

| 维度 ID | 中文 | 描述 | 方向 |
| --- | --- | --- | --- |
| `self_protection` | 自我保护 | 面对资源、风险、利益冲突时保护自身权益 | 自我舍弃 ↔ 自我保护 |
| `altruism` | 利他倾向 | 为他人利益牺牲自身资源、时间、机会 | 利己 ↔ 利他 |
| `freedom` | 自由需求 | 对选择权、自主权、不受控制的重视 | 受控 ↔ 自由 |
| `security` | 安全需求 | 对稳定、秩序、风险降低的偏好 | 冒险 ↔ 求稳 |
| `privacy` | 隐私保护 | 对个人信息、身体、思想边界的重视 | 开放 ↔ 边界 |
| `wealth` | 财富偏好 | 对金钱、资源积累、经济收益的重视 | 淡泊 ↔ 逐利 |
| `rule_orientation` | 规则意识 | 对法律、制度、程序、公平的重视 | 变通 ↔ 守规 |
| `pragmatism` | 现实主义 | 关注实际结果、可执行性与现实收益 | 理想 ↔ 务实 |
| `collectivism` | 集体主义 | 优先考虑群体、社会、整体利益 | 个人 ↔ 集体 |
| `long_term` | 长期主义 | 愿牺牲短期收益换取长期价值 | 即时 ↔ 长远 |

> 维度是**连续轴**，不代表好坏。结果只描述倾向，不做道德判断（见 `docs/ResultInterpretation.md`）。

---

## 5. 权重语义与计分

以题 `Q00001` 为例：

```json
"weights": [
  { "dimension": "self_protection", "yes": 5, "no": -5 },
  { "dimension": "altruism", "yes": -3, "no": 3 }
]
```

- 答 **Y** → `self_protection` +5、`altruism` -3；
- 答 **N** → `self_protection` -5、`altruism` +3。

即每题可同时推动多个维度。**正权重（yes>0）表示「选 Y = 拥抱该维度」；负权重（yes<0）表示「选 Y = 牺牲该维度」**。

---

## 6. 分桶逻辑（重点）

随机组卷采用**维度分层抽样**（见 `docs/QuestionSelection.md`），禁止完全随机。为保证「同一维度 + 同一权重」有多道不同题可抽，题库按如下结构组织：

### 6.1 主维度与主权重桶的判定
- **主维度**：`weights[0].dimension`（权重数组第一条）。
- **主权重桶**：`weights[0].yes` 的取值。
- 桶集合：`{-5, -4, -3, -2, -1, +1, +2, +3, +4, +5}`（0 不作为主权重桶）。

### 6.2 核心批次（batch 01~11）：按维度结构化
10 个维度各自有完整题池，覆盖所有权重桶：

| 维度 | 总题数 | 每个主权重桶题数 |
| --- | --- | --- |
| 9 个维度（除 freedom 外） | 40 | 4 |
| `freedom` | 80 | 8 |

> `freedom` 因补齐了 `freedom` 分类（batch 11）而题池翻倍，同权重题池更丰富。

### 6.3 特殊分类批次（batch 12~13）
| 分类 | 题数 | 桶规则 | 主维度 |
| --- | --- | --- | --- |
| `must`（必答） | 40 | 5 个主权重桶 `{-5,-3,-1,+3,+5}` 各 8 题 | 任意（覆盖全部 10 维度） |
| `experimental`（实验性） | 20 | 不分桶 | 任意 |

- `must` 类题目建议**固定出现在每张试卷**（作为锚定/必答题）。
- `experimental` 类建议默认关闭或单独计权，用于试运行。

### 6.4 全量主维度分布（500 题）

| 维度 | 题数 |
| --- | --- |
| `freedom` | 88 |
| `altruism` | 47 |
| `security` | 47 |
| `privacy` | 47 |
| `wealth` | 47 |
| `rule_orientation` | 46 |
| `collectivism` | 46 |
| `self_protection` | 45 |
| `pragmatism` | 44 |
| `long_term` | 43 |

（核心批次为每个维度 40 / freedom 80；`must` 与 `experimental` 的主维度额外叠加在上面。）

### 6.5 分类与难度统计
- 分类分布：`social` 75、`future` 69、`morality` 57、`control` 56、`wealth` 45、`freedom` 40、`must` 40、`risk` 36、`safety` 27、`personal_boundary` 20、`experimental` 20、`privacy` 15。
- 难度分布：`easy` 184、`medium` 116、`hard` 200。

---

## 7. 随机组卷建议（分层抽样）

```
选择测试长度（如 N 题）
↓
确定各维度配额（每个被测维度抽若干题）
↓
每个维度内，按主权重桶分层随机抽题
  （例如 privacy 需抽 8 题 → 从 -5/-3/-1/+1/+3/+5 桶中均衡抽取）
↓
检查重复与覆盖（同一张卷不出现重复 id）
↓
生成试卷
```

要点：

1. **按维度配额**抽题，不要全局随机，保证结果可比较（`docs/QuestionSelection.md`）。
2. 每个维度的桶有 4~8 道不同情境的题，可保证「题目不同、结果可比」。
3. 建议每卷**固定加入全部 `must` 题**（或从中固定抽一部分）。
4. `experimental` 题可独立控制是否进入正式卷。
5. 用 `id` 去重，避免同卷重复。

---

## 8. 校验规则（入库约束）

生成时由 `tools/build_questions.py` 校验，后端读取时也可自行校验：

- `id` 唯一且连续；
- `type` 必须为 `"YN"`；
- `category`、`difficulty` 取值合法；
- `weights` 非空，`dimension` 属于 10 个核心维度，同题不重复；
- 每条权重 `-5 ≤ yes/no ≤ 5`，且 `yes`、`no` 不同时为 0；
- `content` 非空且全库不重复。

---

## 9. 统计扩展（可选）

题可在运行时附加统计信息，用于低区分度题淘汰与权重校准：

```json
"statistics": {
  "answer_yes_rate": 0.52,   // 实测答 Y 比例（理想约 0.5，避免全员同答案）
  "discrimination": 0.71,    // 区分度
  "sample_count": 10000
}
```

---

## 10. 后端集成注意事项

1. **数据源**：仅读取 `question-bank/questions.json`（UTF-8，`ensure_ascii=false` 的中文原文）。
2. **作答模型**：每题记录 `id + 答案(Y/N)` 即可；计分时对每条 `weights` 累加 `yes` 或 `no`。
3. **维度打分**：按维度聚合累加，得到各维度总分；可再按题数归一化。
4. **矛盾分析**：允许同一维度内正负冲突，结果解释需给出「情境依赖」提示（`docs/ResultInterpretation.md`）。
5. **`must` / `experimental`**：如需差异化处理，按 `category` 字段过滤。
6. 任何改动题库后，请保持 `id` 连续、桶结构完整，并重跑校验。

---

## 11. 重新生成题库（仅本地）

`drafts/` 与 `tools/` 为本地工作目录（已 `.gitignore`），不随仓库分发。若在本地修改题目后需重新生成正式题库：

```bash
cd question-bank
python tools/build_questions.py   # 合并 + 校验，输出 questions.json
```

脚本会校验总数、维度桶结构、must 桶规则、experimental 数量等，全部通过才写出 `questions.json`。
