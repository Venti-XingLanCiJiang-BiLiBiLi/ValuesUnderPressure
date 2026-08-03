# 更新日志（Changelog）

本文件记录取舍之间 (Values Under Pressure, VUP) 项目的变更（题库、后端、前端与部署）。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [0.5.1] - 2026-08-03

### 新增

- **维度筛选组卷**（`backend/app/selection.py`）：`POST /api/test/session` 的 `dimensions` 参数从"仅 API 兼容保留"变为实际生效。指定维度后仅抽取匹配题目，缺口按常规 → must → experimental 优先级回补。

### 修复

- **`db.py`**：`datetime.datetime.utcnow()` → `datetime.datetime.now(datetime.UTC)`（Python 3.12+ 弃用警告）。
- **`main.py`**：`@app.on_event("startup")` → `lifespan` context manager（FastAPI 弃用警告）。
- **`selection.py`** 回补缺口改为三级分层优先级（常规分类 → must → experimental），避免回补时混入 must/experimental 题稀释试卷结构。
- **`ResultView.vue`** `uncertain_dimensions` 区块文案：标题从"数据不足的维度"改为"作答一致性偏低的维度"，描述从"作答题数过少"改为"作答方向不一致，可能受具体情境影响较大"（该列表实际是由低一致性触发，并非题数少）。
- **`theme.ts`** `CONSISTENCY_THRESHOLDS.moderate` 从 0.6 改为 0.5，与后端 `scoring.py` 的 `CONSISTENCY_LOW_THRESHOLD` 对齐，消除 DimensionBar"情境依赖"标签与 uncertain_dimensions 列表的不一致。
- **结果页刷新恢复**（`useSessionRestore.ts` / `test.ts` / `App.vue` / `ResultView.vue`）：测试结果缓存到 sessionStorage，刷新结果页无需后端即可恢复展示。

### 清理

- 删除空目录 `backend/app/routers/`（重构遗留）。

## [0.5.0] - 2026-08-03

### 变更

- **组卷算法重构**（`backend/app/selection.py`）：由「按维度分层」改为「**按场景分类 + 难度分层**」抽题，默认试卷题量由 40 增至 **50 题**。
  - `must`：40 题按顺序每 4 题一桶（`Q00441-444`、`Q00445-448`…）各抽 1 题，得 10 个候选后再随机取 **5 题**（用于跨用户锚定）。
  - `experimental`：固定随机抽 **1 题**。
  - 其余 10 个常规分类：每类随机抽 **4~5 题**（随机挑 4 类各 5 题、6 类各 4 题，合计 44 题）。
  - 常规分类内**按难度（easy/medium/hard）比例分层采样**（最大余数法）：稀缺难度不过度采样，某难度不足时用同类其余题目补齐。
- 后端 `POST /api/test/session` 默认题量 40 → **50**；前端默认/推荐题量同步为 **50**。
- 前端题量选项由 20/40/60 调整为 **30 / 50 / 70**（默认 50，标为「推荐」）。

### 测试

- 重写 `backend/tests/test_selection.py`：覆盖 must 桶抽题、seed 可复现、分类配额（默认 50 = 5 + 1 + 44）、难度分层采样，直接使用正式题库（`question-bank/questions.json`）。
- 后端完整测试通过（34 项）。

### 文档

- `docs/QuestionSelection.md` 更新为「按场景分类 + 难度分层」组卷说明。

## [0.4.0] - 2026-08-03

### 新增

- 前端「取舍之间 · 价值观压力测试」（`frontend/`）：Vue 3 + TypeScript + Vite + TailwindCSS + Pinia + Vue Router。
  - 完整测试流程：开屏题量选择（20/40/60）→ 逐题 Y/N 作答 → 维度画像 + 矛盾分析结果页。
  - 深色 / 浅色主题切换、断线会话恢复（sessionStorage + 后端会话校验）。
- GitHub Pages 部署工作流 `.github/workflows/deploy-frontend.yml`：push 到 `main`（涉及 `frontend/**`）时自动构建并部署前端静态站点，支持手动触发。

### 变更

- 仓库更名为 **`ValuesUnderPressure`**，产品统一命名为「取舍之间 · Values Under Pressure (VUP)」。
- 前端路由改为 **hash 模式**（`#/test`、`#/result`），兼容 GitHub Pages 静态托管的刷新与直达。
- 主 `README.md` 同步前端页面名称与 GitHub Pages 部署说明。

### 说明

- GitHub Pages 为纯静态托管，**不含后端**；完整功能需另行部署后端并以 `VITE_API_BASE_URL` 指向其地址（详见 `frontend/README.md`）。

## [0.3.1] - 2026-08-03

### 变更

- 新增 `.gitignore`：忽略题库生成工作目录 `question-bank/drafts/` 与 `question-bank/tools/`。
- 将 `question-bank/drafts/`、`question-bank/tools/` 移出 Git 版本控制（本地文件保留，仅正式题库 `question-bank/questions.json` 入库）。
- 新增 `question-bank/README.md`：题库格式、分桶/维度逻辑、随机组卷与后端集成说明。
- 新增本文件 `CHANGELOG.md`。
- 批次源文件 JSON 经格式化（仅格式调整，题目内容与权重不变），并已重新合并校验通过（500 题）。

## [0.3.0] - 2026-08-03

### 新增

- 必答分类 `must`：40 题（`Q00441`~`Q00480`），5 个主权重桶（`-5/-3/-1/+3/+5`）各 8 题，主维度覆盖全部 10 个维度。
- 实验性分类 `experimental`：20 题（`Q00481`~`Q00500`），不分桶，自由生成（含记忆读取、机器人管家、天赋转移、算法规划人生等抽象情境）。
- 校验脚本支持特殊批次单独校验（`must` 桶规则 / `experimental` 不分桶）。

### 变更

- 题库总量由 440 增至 **500 题**。
- 分类由 10 类增至 12 类（新增 `must`、`experimental`）。

## [0.2.0] - 2026-08-03

### 新增

- 补齐 `freedom` 分类：40 题（`Q00401`~`Q00440`），主维度 `freedom`（各权重桶 8 题）。
- 10 个原始分类全部覆盖。

### 变更

- 题库总量由 400 增至 **440 题**。
- `freedom` 维度题池由 40 翻倍至 80（每个主权重桶 4 → 8 题）。

## [0.1.0] - 2026-08-03

### 新增

- 初始正式题库：**400 题**（`Q00001`~`Q00400`），10 个核心维度 × 40 题。
- 权重方案：主权重可在 **-5 ~ +5 全范围**取值，每维度 10 个主权重桶 × 4 题。
- 提供题库合并与校验脚本 `question-bank/tools/build_questions.py`。

### 说明

- 题目均为「底线压力测试」：明确交换关系（牺牲 A 换取 B），Y/N 二选一，无对错、不评善恶。
