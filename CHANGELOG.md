# 更新日志（Changelog）

本文件记录取舍之间 (Values Under Pressure, VUP) 项目的变更（题库、后端、前端与部署）。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.2.0] - 2026-08-03

### 新增

- **题目页「上一题 / 下一题」导航**（`frontend/src/views/TestView.vue`、`frontend/src/stores/test.ts`）：
  作答过程中可回退到已答过的题目查看/修改答案（防止误触 Y/N 无法回头）。
  前端按 index 缓存已显示题目；回退后重新作答会覆盖旧答案并自动前进到下一题，
  回退状态显示「下一题」可随时回到进度点。进度条显示实际答题进度，不因回退查看而倒退。

### 修复

- **一致性（置信度）算法过于敏感且有误**（`backend/app/scoring.py`、`backend/tests/test_scoring.py`）：
  一致性从「按贡献权重大小加权」改为「按作答方向符号统计」：对每个维度记录每题方向，
  比较各题方向代数和与绝对值代数和的差距（`|Σ sign| / n`）。不受单题权重大小影响，
  避免「9 题 8 同向」这类稳定作答因大权重反向题被误判为情境依赖，整体置信度不再被异常拉低。
- **倾向分类阈值残留 70/30**（`backend/README.md`）：矛盾分析文案中「高分区间（≥70）」
  改为「≥60」，与 `scoring.py` 的 `HIGH_SCORE_THRESHOLD=60` / `LOW_SCORE_THRESHOLD=40` 对齐。
- **深色/浅色模式下按钮不可见**（`frontend/src/style.css`）：`btn-ghost` 增加 `ring` 边框
  （浅色 `ring-ink-300` / 深色 `ring-ink-600`），删除存档、复制链接等无底色按钮在两种主题下均可辨认。
- **题目页选项配色**（`frontend/src/style.css`）：作答按钮改为「Y = 绿色（赞同）」、
  「N = 红色（反对）」，两钮视觉对等、均无默认选中态。

### 变更

- `frontend/src/components/DimensionBar.vue`：修正一致性配色注释（`0.6` → `0.5`），
  与 `theme.ts` 的 `CONSISTENCY_THRESHOLDS` 及后端 `CONSISTENCY_LOW_THRESHOLD` 对齐。

## [1.1.0] - 2026-08-03

### 新增

- **本地存档功能**（`frontend/`）：
  - 新增 `frontend/src/composables/useArchives.ts`：测试完成后结果自动保存到浏览器 **localStorage**（按 session 去重、最新在前、最多保留 50 条），仅存本机、不上传服务器，便于长期回顾。
  - 首页（`IntroView.vue`）新增「📁 我的存档」区块：按时间列出历史结果（题数 / 置信度 / 分数最高 3 维），可一键「查看」或「删除」。
  - 新增存档查看页 `/archive/:sessionId`（`frontend/src/views/ArchiveView.vue`）：完整展示单次结果（概览三卡 / 10 维度 / 矛盾分析 / 不确定维度），支持返回首页与删除存档。
  - 结果渲染抽成共享组件 `ResultContent.vue`，结果页与存档页复用，保证两处展示一致。

### 变更

- **结果页维度展示改版**（`frontend/src/components/ResultContent.vue`、`DimensionBar.vue`、`config/theme.ts`）：
  - 排序由「原始分降序」改为「偏离中间值 50 的绝对值（`|score-50|`）降序」，倾向越极端排越前。
  - 条形图由「长度=原始分」改为**以 50 为中线向左右两侧展开的对称条形图**：低分向左、高分向右，条长表示偏离程度，越贴近 50 条越短、越极端越长；渐变方向让远离中线的尖端颜色最深。
  - 配色阈值调整：>60 蓝色渐变（高分倾向）、<40 粉色渐变（低分倾向）、40~60 灰色渐变（中间）。
  - 后端倾向分类阈值与配色阈值对齐（`backend/app/scoring.py`）：`HIGH_SCORE_THRESHOLD` 70 → 60、`LOW_SCORE_THRESHOLD` 30 → 40，使「倾向」标签（高分/低分/中间地带）与条形配色判定一致。
- 项目版本号 `1.0.0` → `1.1.0`（`frontend/package.json`）。

### 说明

- 存档依赖浏览器本地存储，清理浏览器站点数据会一并清除；多设备间不互通。

## [1.0.0] - 2026-08-03

### 新增

- **一键部署（Docker Compose）**：前后端容器化，单命令部署到云服务器或本地 Docker Desktop。
  - `backend/Dockerfile`：Python 3.11-slim 镜像，打包后端代码与正式题库（`question-bank/questions.json`），`APP_ENV=production` 禁止回退开发样例题库；SQLite 数据落盘于命名卷。
  - `frontend/Dockerfile` + `frontend/nginx.conf`：多阶段构建（Node 22 构建 Vite 产物 → Nginx 托管），同源反代 `/api` 到后端，Vue Router history 回退，单端口暴露、无跨域。
  - `docker-compose.yml`：编排 `backend` + `frontend`，数据持久化于命名卷 `vup-data`，内置健康检查，容器重建/升级不丢数据。
  - `deploy/` 目录：`deploy.sh`（Linux 云服务器）、`deploy.ps1`（Windows + Docker Desktop 本地自测）、`backup.sh`（数据库备份，保留最近 14 份）、`wait-docker.ps1`（等待引擎就绪）、`.env.example`（部署配置样例）。
  - 根 `README.md` 新增「一键部署（Docker Compose）」章节，含 Linux 部署、Windows 本地自测与定时备份说明。

### 变更

- 项目正式发布 **1.0.0**：`frontend/package.json` 版本号 `0.1.0` → `1.0.0`。
- `frontend/tsconfig.json`：移除已弃用的 `baseUrl`，`paths` 改用 `"@/*": ["./src/*"]`（无 `baseUrl` 时相对 tsconfig 目录解析），消除 TypeScript 6/7 弃用警告。

### 说明

- 构建镜像需能访问 Docker Hub；国内网络不可达时，请在 Docker daemon 中配置镜像加速器（如 DaoCloud `https://docker.m.daocloud.io`）。

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
