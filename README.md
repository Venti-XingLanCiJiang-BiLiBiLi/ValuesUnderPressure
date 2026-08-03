# aPersonalityTest

基于**极端价值冲突场景**的价值观压力测试 + 多维人格画像。

通过 Y/N 二选一作答，测量用户在 10 个核心价值维度上的底线与优先级。**不是 MBTI / 人格分类测试**——结果只描述倾向，不做人格定性判断，允许不同情境下出现矛盾。

## 项目结构

```
aPersonalityTest/
├── backend/          # FastAPI 后端服务（组卷、作答、计分、结果解读）
├── question-bank/    # 题库数据与题库管理（与代码分离）
├── frontend/         # 前端项目（规划中，当前为空）
├── docs/             # 设计文档（测试机制、评分算法、API、数据库等）
└── README.md
```

## 题库与代码分离

**题库是数据，不是代码。**

- 正式题库独立存放于 `question-bank/questions.json`（500 题，`Q00001`~`Q00500`），后端与前端统一从此读取，避免在代码库中维护多份副本。
- 题目格式定义见 `question-bank/schema.json`（每个问题可同时影响多个维度，支持 yes/no 双向、正负权重）。
- 题目结构说明见 `question-bank/question_bank_readme.md`。
- `backend/app/data/questions.json` 仅为**开发环境回退样例**（真实题库的子集），用于正式题库缺失时让服务可启动；它不是正式题库。
- 题库生成工作目录（`question-bank/drafts/`、`question-bank/tools/`）不随仓库分发，已加入 `.gitignore`。

## 快速开始（后端）

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

启动后访问：

- API 文档：http://127.0.0.1:8000/docs
- 健康检查：http://127.0.0.1:8000/api/health

## 文档索引

| 文档 | 内容 |
| --- | --- |
| `docs/TestDesign.md` | 测试机制与设计原则 |
| `docs/DimensionSystem.md` | 10 个核心价值维度定义 |
| `docs/ScoringAlgorithm.md` | 累加 + 归一化 + 一致性算法 |
| `docs/API.md` | REST 接口约定 |
| `docs/QuestionBankSchema.md` | 题库数据结构 |
| `docs/DatabaseSchema.md` | 数据库表结构 |
| `question-bank/question_bank_readme.md` | 题库维护说明 |
