# 更新日志（Changelog）

本文件记录取舍之间 (Values Under Pressure, VUP) 项目的变更（题库、后端、前端与部署）。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

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
