# 性格测试题库存储格式设计文档

## 设计目标

本测试通过 Y/N 极端情境问题探测用户价值排序与底线边界。

题库支持：

- 单题多维度影响
- 正负权重
- 分层随机组卷
- 数据统计与权重校准

## 数据结构

### Question

```json
{
  "id": "Q00001",
  "content": "你愿意公开自己全部健康记录，换取一笔巨款吗？",
  "type": "YN",
  "category": "personal_boundary",
  "difficulty": "medium",
  "tags": ["privacy", "money"],
  "weights": [
    {
      "dimension": "privacy",
      "yes": -5,
      "no": 5
    },
    {
      "dimension": "money",
      "yes": 3,
      "no": -1
    }
  ]
}
```

## 题库版本清单（manifest.json）

每个题库版本目录（`question-bank/<version>/`）除 `questions.json` / `dimensions.json` /
`questions.index.json` 外，还包含 `manifest.json`（版本清单），用于保证 `questions.json`
与 `dimensions.json` 属于同一题库版本：

```json
{
  "schema_version": "1",
  "bank_version": "v1",
  "questions_file": "questions.json",
  "dimensions_file": "dimensions.json",
  "questions_sha256": "e38f...f685",
  "dimensions_sha256": "34a0...3fa"
}
```

| 字段 | 说明 |
| --- | --- |
| `schema_version` | manifest 结构版本（当前 `"1"`），升级结构时递增 |
| `bank_version` | 题库版本名（对应版本目录名，如 `v1`） |
| `questions_file` | 题目文件名引用（通常 `questions.json`） |
| `dimensions_file` | 维度文件名引用（通常 `dimensions.json`） |
| `questions_sha256` | `questions.json` 的 sha256 摘要 |
| `dimensions_sha256` | `dimensions.json` 的 sha256 摘要 |

校验逻辑见 `docs/DataValidation.md` 第 6 节与 `backend/app/manifest.py`；生成方式：
`python scripts/generate_manifest.py [bank_dir]`，或运行各版本 `build_questions.py`
（生成 `questions.json` 后自动联动产出 manifest）。

## 权重规则

推荐范围：

-5 强烈倾向
-3 明显倾向
-1 轻微倾向
0 无影响
+1 轻微倾向
+3 明显倾向
+5 强烈倾向

选择 Y 使用 yes 权重，选择 N 使用 no 权重。

## 多维度模型

问题可以同时影响多个维度，例如：

- 隐私保护
- 财富偏好
- 自我边界
- 利他倾向
- 集体主义

## 随机组卷

禁止完全随机抽题。

采用维度分层随机：

- 隐私
- 自由
- 利他
- 规则
- 财富

保证不同用户题目不同，同时结果可比较。

## 统计扩展

```json
{
  "statistics": {
    "answer_yes_rate": 0.52,
    "discrimination": 0.71,
    "sample_count": 10000
  }
}
```

用于筛选低区分度题目和优化权重。

## 原则

1. 测量价值排序，不判断善恶。
2. 单题只贡献数据，不决定人格。
3. 权重通过真实用户数据持续校准。
