# 性格测试题库说明（question-bank）

本目录下的 `questions.json` 是取舍之间 (Values Under Pressure, VUP) 项目的**正式题库**，供后端组卷、计分与统计使用。

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
  "tags": ["self_protection", "altruism"],  // 检索与分析标签
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
用于检索、过滤和统计分析的标签列表。可包含维度标签，但不要求与 `weights` 中的 `dimension` 完全一致。

例如：

```json
"tags": ["privacy", "family", "self_sacrifice"]
```

其中 `privacy` 可以对应权重维度，`family`、`self_sacrifice` 可以用于描述题目语义。

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

字段说明：

- `version`：数据结构版本，用于追踪 schema 变化；
- `status`：题目生命周期状态。

允许值：

| status | 含义 |
| --- | --- |
| `draft` | 草稿，未进入正式测试 |
| `active` | 正式启用 |
| `experimental` | 实验运行，可单独控制 |
| `deprecated` | 已废弃，不再组卷 |

统计扩展见 §9。

---

（其余章节保持原文不变。）
