# 取舍之间 (Values Under Pressure) 后端

本目录是根据仓库内 **所有 `.md` 设计文档** 梳理出开发目标后实现的后端服务。

## 1. 开发目标（来自仓库文档梳理）

| 文档 | 明确的目标 |
|---|---|
| `docs/QuestionBankSchema.md`, `question-bank/question_bank_readme.md` | 题库数据结构：单题多维度权重（-5~+5）、12 个场景分类、`must`/`experimental` 特殊分类 |
| `docs/DimensionSystem.md` | 10 个核心价值维度（self_protection / altruism / freedom / security / privacy / wealth / rule_orientation / pragmatism / collectivism / long_term），维度是连续轴，不代表好坏 |
| `docs/DataValidation.md` | 题库加载时必须做 schema 校验、权重范围校验（-5~+5，yes/no 不同时为 0，维度不重复） |
| `docs/QuestionSelection.md` | **禁止**全局随机抽题，必须按分桶索引桶驱动组卷，保证跨用户可比较 |
| `docs/TestDesign.md` | 测试会话生命周期：创建会话 → 桶驱动组卷 → 作答 Y/N → 计分 → 一致性分析 → 生成结果 |
| `docs/ScoringAlgorithm.md` | 按权重累加 → 归一化到 0-100 → 一致性分析 |
| `docs/ResultInterpretation.md` | 结果只描述倾向，不做人格定性；输出矛盾组合分析与"情境依赖"提示 |
| `docs/DatabaseSchema.md` | sessions / answers / results 持久化表结构，题库版本可追溯 |
| `docs/API.md` | REST 接口形状：创建会话 / 取题 / 提交答案 / 取结果 |
| `docs/Analytics.md`, `docs/Calibration.md` | （后续迭代方向，未在本次后端中实现，见下方"未覆盖范围"） |

据此，本后端实现了一个可运行的 **FastAPI + SQLite** 服务，完整覆盖题库加载校验、桶驱动组卷、作答、计分与结果解读的闭环。

## 2. 目录结构

```
backend/
├── app/
│   ├── main.py            # FastAPI 路由 (对应 docs/API.md)
│   ├── db.py               # SQLite 持久化 (对应 docs/DatabaseSchema.md)
│   ├── dimensions.py        # 10 个核心维度的静态元数据 + 矛盾组合表
│   ├── question_bank.py     # 题库加载（分桶索引 + 按需加载桶）+ 校验 (docs/DataValidation.md)
│   ├── selection.py         # 桶驱动随机组卷（依赖分桶索引）(对应 docs/QuestionSelection.md)
│   ├── scoring.py           # 计分 / 归一化 / 一致性 / 结果解读
│   ├── schemas.py           # Pydantic 请求/响应模型
│   └── data/
│       └── questions.json   # 开发回退样例题库（正式题库见 question-bank/questions.json）
├── scripts/
│   ├── validate_bank.py     # 独立题库校验 CLI
│   └── smoke_test.py        # 不依赖 FastAPI 的核心流程冒烟测试
└── requirements.txt
```

## 3. 题库读取（题库与代码分离）

**正式题库按版本目录独立存放于仓库根目录 `question-bank/<version>/`**（当前 `v1/`，500 题）。
后端抽题**依赖分桶索引** `question-bank/<version>/questions.index.json`（结构记录：
各组题数 / 桶数 / 每桶数量 / 文件位置），按需懒加载桶文件，不再全量加载 `questions.json`。

> `@deprecated`：版本目录内的 `questions.json`（合并产物/构建快照）已被分桶索引取代，
> **前后端正常运行都不依赖它**。仅保留兼容：`scripts/validate_bank.py` 全量校验、
> 分桶索引缺失时的开发回退，以及旧接口 `load_question_bank` / `QuestionBank`（测试用）。
> 后端抽题入口为 `load_bucket_bank()` / `BucketBank`。

`app/question_bank.py` 加载抽题数据源（`load_bucket_bank`）的优先级：

1. 显式传入的 `path` 或环境变量 `QUESTION_BANK_PATH`（自定义/测试题库文件，构建虚拟索引）；
2. **正式路径**：`question-bank/<QUESTION_BANK_VERSION>/questions.index.json`
   （分桶索引；`QUESTION_BANK_VERSION` 默认 `v1`，可由 Docker/环境变量控制）；
3. **开发回退**（`@deprecated`）：同版本目录的 `questions.json`（构建虚拟索引）或 `app/data/questions.json`。

启动时日志会明确标注加载来源：

```text
INFO:question_bank:Loaded bank index: .../question-bank/v1/questions.index.json
# 或
INFO:question_bank:Loaded bucket bank from custom file: .../tests/fixtures/questions.json
```

> `QUESTION_BANK_VERSION` 控制题库版本（默认 `v1`）；`app/data/questions.json` 只是
> **开发回退样例**（真实题库的子集），不应把正式题库复制到两处——正式数据一律以
> `question-bank/<version>/` 为准。

**生产/开发回退行为**：设置环境变量 `APP_ENV=production`（或 `prod`）时，若版本分桶索引
缺失，后端会直接报错退出，**禁止静默回退**到开发样例；未设置 `APP_ENV`（默认开发环境）
时才允许回退（同版本 `questions.json` 或 `app/data/questions.json`），保证本地/测试可启动。

题库加载时会自动执行 `docs/DataValidation.md` 中的规则；不满足规则的题目会被
跳过并记录原因（见 `/api/health` 或 `scripts/validate_bank.py` 输出），不会导致
服务整体启动失败。

## 4. 运行

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

不依赖 Web 框架的核心逻辑自测（当前沙盒环境已验证通过）：

```bash
python scripts/smoke_test.py
python scripts/validate_bank.py
```

## 5. API（对应 docs/API.md，并补充了健壮性字段）

### 创建测试会话
```
POST /api/test/session
Body: {"length": 50, "dimensions": null}   # dimensions 可选，默认覆盖全部 10 维度
-> {"session_id": "...", "question_count": 50}
```

### 获取下一题
```
GET /api/test/session/{id}/question
-> {"question_id": "Q00001", "content": "...", "type": "YN", "index": 0, "total": 50}
```
若已答完全部题目，返回 409。

### 提交答案
```
POST /api/test/session/{id}/answer
Body: {"question_id": "Q00001", "answer": "Y", "duration": 8}
-> {"status": "ok", "answered_count": 1, "total": 50, "completed": false,
    "answer_history": []}
```
允许修改已提交的答案：修改不改变进度，但会写入 `answer_history`（旧答案、新答案、修改时间）。
当前答案与完整修改历史见 `GET /api/test/session/{id}/answers`。

### 获取结果
```
GET /api/test/session/{id}/result
-> {
     "session_id": "...",
     "completed": true,
     "dimensions": {
       "privacy": {"dimension": "privacy", "name": "隐私保护", "score": 82.0,
                    "tendency": "隐私保护", "description": "...",
                    "consistency": 0.83, "question_count": 4, "confidence": 0.8}
     },
     "confidence": 0.78,
     "conflicts": [
       {"dimensions": ["freedom", "security"], "names": ["自由需求", "安全需求"],
        "description": "..."}
     ],
     "uncertain_dimensions": []
   }
```
每个维度额外返回 0~1 的 `confidence`（维度级可信度，综合题量 / 一致性 / 权重覆盖）。
未作答全部题目时返回 HTTP 409，不输出部分画像。

### 其它
- `GET /api/health` — 服务与题库加载状态
- `GET /api/dimensions` — 10 个核心维度的说明

## 6. 关键设计取舍

- **桶驱动组卷（依赖分桶索引）**：默认 50 题 = `must` 5 + `experimental` 1 + 常规 10 维度 44。
  - 抽题只读取分桶索引 `questions.index.json`（各组题数 / 桶数 / 每桶数量 / 文件位置），按需懒加载桶文件，不加载全量题库；
  - `must`（10 桶 40 题）桶驱动抽 5 题作锚定；`experimental`（不分桶 20 题）固定抽 1 题；
  - 其余 10 个维度组随机挑 4 维各抽 5 题、6 维各抽 4 题；
  - 每个维度组内「先抽 k = min(n, m) 桶 → 候选不足重复抽桶 → 桶内随机取题不重复」；
  - 组内题数不足（d < n）按 fallback 补齐（维度组 → must → experimental）；整卷最后去重校验；
  - 不再按难度（easy/medium/hard）分层抽取。
  这满足了 `docs/QuestionSelection.md` 里"桶驱动随机、覆盖可比较"的要求，
  同时避免"全局随机抽 N 题"导致维度缺失。
- **归一化**：`score = (raw - min_possible) / (max_possible - min_possible) * 100`，
  其中 `min_possible` / `max_possible` 按**本次试卷实际抽中的题目**动态计算，
  而不是针对整个题库的理论极值——因为不同用户的试卷题目不同，用"本次试卷"的
  极值做分母才能保证 0-100 分数在该用户自己的试卷内有意义。
- **一致性 (consistency)**：同一维度内多题作答方向的代数和与绝对值代数和的差距
  （`|Σ sign| / n`，只按方向符号统计、不受权重大小影响），用来判断该维度
  是"稳定倾向"还是"情境依赖"（对应 `docs/ResultInterpretation.md` 的第 5 节）。
  同一维度作答不足 2 题时无法判断，返回 `null`，前端应显示为"数据不足"而非 0。
- **矛盾分析**：维护了一张典型冲突维度对照表（自由/安全、利他/自我保护、
  规则/现实主义等），当两个维度同时进入高分区间（≥60）时输出提示，而不是
  给出人格定性结论。
- **可追溯性**：`test_sessions.question_version` 记录题库版本号，
  `test_sessions.question_ids_json` 固化本次试卷的题目顺序，保证同一会话
  多次请求"下一题"/"结果"时口径一致，也便于未来做重测一致性分析。

## 7. 未覆盖范围（有意保留给后续迭代）

以下能力在文档中被描述为"后续扩展/管理端"，本次聚焦于核心答题闭环，未实现：

- `docs/Analytics.md` / `docs/Calibration.md`：面向运营的题目区分度分析、
  权重自动校准 pipeline（建议做成离线批处理任务，读取 `answers` 表产出校准建议，
  经人工审核后生成新的 `question_bank_vN`）。
- 题库管理后台（增删题、版本发布）。
- 多语言题库、A/B 测试题目、动态难度调整（`docs/TestDesign.md` §6"后续扩展"）。
