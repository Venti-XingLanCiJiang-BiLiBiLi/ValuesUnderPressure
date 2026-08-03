# 取舍之间 · 价值观压力测试（Values Under Pressure · VUP）

基于**极端价值冲突场景**的价值观压力测试 + 多维人格画像。

通过 Y/N 二选一作答，测量用户在 10 个核心价值维度上的底线与优先级。**不是 MBTI / 人格分类测试**——结果只描述倾向，不做人格定性判断，允许不同情境下出现矛盾。

> 仓库：`ValuesUnderPressure` · 在线体验：<https://Venti-XingLanCiJiang-BiLiBiLi.github.io/ValuesUnderPressure/>

## 功能特性

- **10 个核心价值维度**：自我保护 🛡️ / 利他 🤝 / 自由 🕊️ / 安全 🔒 / 隐私 👁️ / 财富 💰 / 规则 ⚖️ / 务实 🎯 / 集体 👥 / 长期 🌱
- **Y/N 二选一**：极端两难情境，无正确答案、不评善恶，只记录你的取舍
- **题量可选**：20 / 40 / 60 题
- **结果只描述倾向**：10 维度画像 + 矛盾组合分析 + 情境依赖提示，不做人格定性
- **题库与代码分离**：500 题独立于代码库，按维度分层组卷，跨用户可比较
- **深色 / 浅色主题**、**断线会话恢复**

## 技术栈

| 端 | 技术 |
| --- | --- |
| 前端 | Vue 3 · TypeScript · Vite · TailwindCSS · Pinia · Vue Router |
| 后端 | FastAPI · SQLite |
| 部署 | GitHub Actions → GitHub Pages（前端静态站点） |

## 项目结构

```
ValuesUnderPressure/
├── backend/          # FastAPI 后端服务（组卷、作答、计分、结果解读）
├── frontend/         # 前端「取舍之间 · 价值观压力测试」（Vue 3 + Vite + TS）
├── question-bank/    # 题库数据与题库管理（与代码分离）
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

## 快速开始（前端）

```bash
cd frontend
npm install
npm run dev
```

打开 http://127.0.0.1:5173（开发环境 `/api` 已代理到本地后端）。生产构建与部署详见 `frontend/README.md`。

## 在线体验（GitHub Pages）

前端静态站点通过 CI 工作流（`.github/workflows/deploy-frontend.yml`）自动部署到 GitHub Pages：

- 访问地址：<https://Venti-XingLanCiJiang-BiLiBiLi.github.io/ValuesUnderPressure/>
- 注意：GitHub Pages 是**纯静态托管，不含后端**。未配置 `VITE_API_BASE_URL` 时仅能浏览页面；完整功能需另行部署后端（Render / Railway / VPS 等）并用该变量指向后端地址，详见 `frontend/README.md`。

## 测试与校验

```bash
# 题库合并与格式校验（生成正式题库）
cd question-bank && python tools/build_questions.py

# 题库加载校验 + 核心流程冒烟测试（backend 目录下）
cd ../backend
python scripts/validate_bank.py    # 退出码 0 通过；1 表示存在被剔除题目
python scripts/smoke_test.py      # 端到端冒烟：创建会话 → 取题 → 提交答案 → 拿结果
```

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

## 许可证

[GPL-3.0](./LICENSE)
