# 性格测试题库说明（question-bank）

本目录下的 `questions.json` 是取舍之间 (Values Under Pressure, VUP) 项目的**正式题库**，供后端组卷、计分与统计使用。

- 测试机制：通过**极端价值冲突场景**中的 Y/N 二选一，测量用户在 10 个价值维度上的底线与优先级。
- 设计原则：**无绝对正确答案、不评价善恶、不测知识**，只测价值排序，允许不同情境下出现矛盾。

---

## 1. 文件与数据来源

题库采用**版本文件夹 + 分桶管理**：每个题库版本一个文件夹（如 `v1/`），版本内题目按主维度拆分到 `questions/` 目录下的多个桶文件（每桶 4 题），由版本内构建脚本合并校验后生成该版本的正式题库 `questions.json`。

| 文件 | 说明 |
| --- | --- |
| `v1/` | **题库版本 v1**（当前正式版本）：包含分桶源文件、构建脚本与合并产物 |
| `v1/questions/` | **分桶源文件**（按主维度分目录，每桶 4 题；`freedom` 每桶 8 题拆 2 桶；`must` 40 题拆 10 桶；`experimental` 20 题不分桶），随仓库入库 |
| `v1/questions.json` | **合并产物 / 构建快照**（`@deprecated`，500 题，`Q00001`~`Q00500`）：仅用于全量校验（`validate_bank.py`）与分桶索引缺失时的开发回退；**非抽题运行时数据源**（前后端正常运行不依赖它） |
| `v1/questions.index.json` | **分桶索引（抽题主数据源）**：记录各组题数、桶（bank）数、每桶数量与文件位置；后端按此懒加载桶文件 |
| `v1/dimensions.json` | **维度元数据（单一数据源）**：英文维度 ID → 中文 name/description/direction 等；后端 `GET /api/dimensions` 与构建脚本均以它为权威 |
| `v1/manifest.json` | **版本清单（manifest）**：记录 `questions.json` / `dimensions.json` 的 sha256，供 `scripts/validate_bank.py` 校验两者属于同一题库版本，避免版本与维度定义不匹配 |
| `v1/build_questions.py` | 合并 + 校验脚本（入库），从 `questions/` 构建 `questions.json` 与 `questions.index.json` |
| `templates/` | **范例题库框架**：与版本目录同构的模板框架，演示分层分桶 + 构建脚本 + 索引 + manifest（全占位数据，可直接复制为新版本骨架） |
| `schema.json` | 题目数据结构规范（版本无关的字段约束） |
| `drafts/` | 历史中间批次源文件（**已废弃，本地保留，不入库**，已加入 `.gitignore`） |

> 后端**抽题**依赖分桶索引 `questions.index.json`（懒加载桶文件）；`questions.json` 为合并快照，仅用于全量校验（`scripts/validate_bank.py`）与索引缺失时的开发回退，**不是抽题数据源**。
> 维护题库时**不要直接改 `questions.json`**，而是编辑对应版本 `questions/` 下的桶文件，再运行该版本下的 `python build_questions.py` 重新生成（同时产出 `questions.json` 与 `questions.index.json`）。
> 修改 `questions.json` 或 `dimensions.json` 后，记得重新生成 manifest（`python scripts/generate_manifest.py`），否则 `scripts/validate_bank.py` 的 sha256 校验会失败。
> **维度元数据**（英文 ID → 中文名称/描述/方向等）维护在各版本的 `dimensions.json`，与题目同版本管理；后端 `GET /api/dimensions` 与构建脚本均以它为单一数据源——修改维度名称/描述只需改该文件。

### 1.1 版本目录结构

```text
question-bank/
├── v1/                        # 题库版本 v1（当前正式版本）
│   ├── questions/
│   │   ├── self_protection/   SP_Bnk-5.json ... SP_Bnk5.json    # 每桶 4 题（主权重桶）
│   │   ├── freedom/           FD_Bnk-5_1.json ... FD_Bnk5_2.json  # 每桶 8 题，拆 2 桶各 4 题
│   │   ├── ...                # 其余维度同 self_protection
│   │   ├── must/              Must_Bnk01.json ... Must_Bnk10.json  # 40 题，每桶 4 题
│   │   └── experimental/      Exp_Bnk01.json                     # 20 题，不分桶
│   ├── dimensions.json        # 维度元数据（英文 ID → 中文名称/描述/方向，单一数据源）
│   ├── manifest.json          # 版本清单：questions.json / dimensions.json 的 sha256
│   ├── questions.json         # 合并后的正式题库（500 题）
│   ├── questions.index.json   # 分桶索引（结构记录）
│   └── build_questions.py     # 从 questions/ 构建 questions.json
├── templates/                 # 范例题库框架（与版本目录同构，全占位数据）
│   ├── questions/
│   │   ├── self_protection/   SP_Bnk-5.json, SP_Bnk5.json   # 2 桶 x 2 题
│   │   └── altruism/          AL_Bnk-5.json, AL_Bnk5.json   # 2 桶 x 2 题
│   ├── dimensions.json        # 维度元数据（模板含 2 维度，结构同 v1）
│   ├── manifest.json          # 版本清单：questions.json / dimensions.json 的 sha256
│   ├── questions.json         # 合并产物（8 题占位）
│   ├── questions.index.json   # 分桶索引（结构记录）
│   └── build_questions.py     # 模板构建脚本（2 维度 x 2 桶 x 2 题）
├── schema.json                # 题目数据结构规范
└── question_bank_readme.md    # 本说明
```

> `templates/` 作为**新版本骨架**：复制为 `v2/` 后，按需增删维度目录与桶文件、调整 `build_questions.py` 顶部的 `DIMENSIONS` / `EXPECTED_PER_BUCKET` / `ID_PREFIX` 等常量，再运行构建、生成 manifest 即可。

- 常规维度目录以维度名命名，桶文件名 `{ABBR}_Bnk{权重}.json`（缩写：`self_protection→SP`、`altruism→AL`、`freedom→FD`、`security→SE`、`privacy→PR`、`wealth→WE`、`rule_orientation→RO`、`pragmatism→PG`、`collectivism→CO`、`long_term→LT`）；
- `freedom` 每个权重桶 8 题，拆成 `FD_Bnk{权重}_1.json` / `FD_Bnk{权重}_2.json` 两个文件（各 4 题）；
- `must` 按 `Q00441~Q00480` 顺序每 4 题一桶，对应后端组卷的 `MUST_BUCKET_SIZE=4` 抽样逻辑；
- `experimental` 20 题不分桶，放单个文件。

### 1.2 新增题库版本

新增一个题库版本（如 `v2`）时：
1. 从 `templates/` 复制框架为 `v2/`（或复制 `v1/` 为 `v2/` 后清空真实题目）；
2. 按需增删 `v2/questions/` 下的维度目录与桶文件，保持每桶题数与 `build_questions.py` 顶部常量（`DIMENSIONS` / `EXPECTED_PER_BUCKET` / `BUCKET_FILE_SIZE` / `ID_PREFIX`）一致、`id` 唯一连续；
3. 运行 `cd v2 && python build_questions.py` 生成 `v2/questions.json` 与 `v2/questions.index.json`；
4. 运行 `python scripts/generate_manifest.py v2` 生成 `v2/manifest.json`（记录 questions/dimensions 的 sha256）；
5. 后端切换数据源为 `v2/questions.json`（读取逻辑更新属后续任务）。

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
