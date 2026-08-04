# 题目合法性校验规则

## 1. 目标

确保题库中的问题具备可计算性、一致性和可维护性。

## 2. Schema 校验

每个问题必须满足：

- id 唯一
- content 非空
- type 必须为 YN
- weights 至少包含一个维度
- dimension 必须存在于 dimensions.json
- metadata.version 必须存在且为正整数
- metadata.status 必须为合法状态

### metadata.status 合法值

| status | 含义 |
| --- | --- |
| draft | 草稿，未进入正式测试 |
| active | 正式启用 |
| experimental | 实验运行，可单独控制 |
| deprecated | 已废弃，不再组卷 |

## 3. 权重校验

规则：

- 单个权重范围：-5 ~ +5
- yes 和 no 不能同时为 0
- 同一 dimension 不允许重复出现
- 问题必须至少影响一个有效维度

## 4. 内容质量检查

禁止：

- 明显诱导答案
- 只有单一价值倾向
- 所有人都会选择同一答案的问题
- 与其他问题高度重复

## 5. 统计校验

上线后根据数据检查：

```json
{
  "answer_yes_rate": 0.5,
  "discrimination": 0.7
}
```

低区分度问题进入淘汰或重新校准流程。

## 6. 题库版本一致性校验（manifest.json）

**目标**：确保 `questions.json` 与 `dimensions.json` 永远属于同一个题库版本，避免
「题库版本与维度定义不匹配」导致测评结果错误。每个题库版本目录下存放 manifest：

```text
question-bank/
  v1/
    manifest.json       # 版本清单
    questions.json
    dimensions.json
```

`manifest.json` 内容：

```json
{
  "schema_version": "1",
  "bank_version": "v1",
  "questions_file": "questions.json",
  "dimensions_file": "dimensions.json",
  "questions_sha256": "...",
  "dimensions_sha256": "..."
}
```

**校验项**（`backend/app/manifest.py` 的 `validate_manifest()`）：

1. 文件存在检查（`manifest.json` 存在且可解析）；
2. `schema_version` 与当前版本一致；
3. `questions_file` / `dimensions_file` 文件名引用检查（引用的文件必须存在）；
4. `questions.json` sha256 校验；
5. `dimensions.json` sha256 校验。

**校验入口**：

- `scripts/validate_bank.py`（默认优先校验 manifest，再全量校验题目；manifest 缺失
  输出明确错误并返回非零退出码）；
- **生产环境运行时**（`APP_ENV=production|prod`）：`load_bucket_bank()` 加载版本目录
  题库前强制校验 manifest，失败即拒绝加载（覆盖启动与热更新 `/api/admin/reload-bank`）；
  自定义 `QUESTION_BANK_PATH` 与开发环境不强制，保持回退与测试便利。

**生成**：`python scripts/generate_manifest.py [bank_dir]`，或直接运行各版本
`build_questions.py`（生成 `questions.json` 后自动联动产出 manifest）。修改
`questions.json` / `dimensions.json` 后必须重新生成 manifest，否则校验失败。
