# 取舍之间 · 价值观压力测试（Values Under Pressure · VUP）

基于**极端价值冲突场景**的价值观压力测试 + 多维人格画像。

通过 Y/N 二选一作答，测量用户在 10 个核心价值维度上的底线与优先级。**不是 MBTI / 人格分类测试**——结果只描述倾向，不做人格定性判断，允许不同情境下出现矛盾。

> 仓库：`ValuesUnderPressure`
## 功能特性

- **10 个核心价值维度**：自我保护 🛡️ / 利他 🤝 / 自由 🕊️ / 安全 🔒 / 隐私 👁️ / 财富 💰 / 规则 ⚖️ / 务实 🎯 / 集体 👥 / 长期 🌱
- **Y/N 二选一**：极端两难情境，无正确答案、不评善恶，只记录你的取舍
- **题量可选**：30 / 50 / 70 题（默认 50），支持按维度筛选组卷
- **结果只描述倾向**：10 维度画像 + 矛盾组合分析 + 情境依赖提示，不做人格定性；维度条以 50 中线向两侧展开、颜色区分倾向强度
- **题库与代码分离**：500 题按版本目录 + 分桶管理，后端抽题依赖分桶索引（`questions.index.json`）桶驱动组卷、按需懒加载桶文件，跨用户可比较（默认 50 题 = 5 锚定 + 1 实验 + 44 常规）
- **可修改答案**：价值观测试不是考试，允许修改已提交的答案，修改记录保留在 `answer_history`，不影响答题进度
- **维度级置信度**：每个维度除分数外，还给出 0~1 的 `confidence`（综合题量、一致性、权重覆盖）
- **本地存档**：答完自动保存结果到本机（localStorage），首页「我的存档」可随时查看 / 删除历史结果
- **深色 / 浅色主题**、**断线会话恢复**、**结果页刷新恢复**

## 技术栈

| 端 | 技术 |
| --- | --- |
| 前端 | Vue 3 · TypeScript · Vite · TailwindCSS · Pinia · Vue Router |
| 后端 | FastAPI · SQLite |
| 部署 | Docker |

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

- 正式题库按版本目录存放于 `question-bank/v1/`，**前后端抽题依赖分桶索引** `v1/questions.index.json`（记录各组题数/桶数/每桶数量/文件位置，懒加载桶文件）；`v1/questions.json`（合并产物/构建快照）已标记 `@deprecated`——**前后端正常运行都不依赖它**，仅保留兼容（全量校验 `scripts/validate_bank.py`、分桶索引缺失时的开发回退、旧接口 `load_question_bank`）。
- 题库按版本文件夹 + 主维度**分桶管理**：题库版本 `v1/` 内含分桶源文件 `v1/questions/`（每桶 4 题，随仓库入库），由 `v1/build_questions.py` 合并生成 `v1/questions.json` 与 `v1/questions.index.json`。范例题库框架（与版本目录同构，全占位数据，可复制为新版本骨架）见 `templates/`。维护题库时编辑分桶文件后重新运行构建脚本。
- 题目格式定义见 `question-bank/schema.json`（每个问题可同时影响多个维度，支持 yes/no 双向、正负权重）。
- 题目结构说明见 `question-bank/question_bank_readme.md`。
- `backend/app/data/questions.json` 仅为**开发环境回退样例**（真实题库的子集），用于正式题库缺失时让服务可启动；它不是正式题库。
- 分桶改造前的历史批次目录（`question-bank/drafts/`）已废弃，不随仓库分发，已加入 `.gitignore`。

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

<http://vup.starrylan.cn/#/test>

## 一键部署（Docker Compose，推荐）

适合自有云服务器（VPS）。前后端打包为两个容器，Nginx 同时托管前端静态文件并反代 `/api` 到后端，**同源部署、单端口暴露、无跨域**；SQLite 数据保存在命名卷中，升级/重启不丢失。

```
ValuesUnderPressure/
├── docker-compose.yml        # 编排：backend + frontend
├── backend/Dockerfile        # Python 3.11 + 后端 + 正式题库
├── frontend/Dockerfile       # 多阶段：Node 构建 → Nginx 托管
├── frontend/nginx.conf       # 静态托管 + /api 反代 + history 回退
└── deploy/
    ├── deploy.sh             # 一键部署（Linux 云服务器）
    ├── deploy.ps1            # 一键部署（Windows + Docker Desktop 本地自测）
    ├── backup.sh             # 数据库备份（Linux：一致性在线备份 + 压缩，保留 14 天）
    ├── backup.ps1            # 数据库备份（Windows + Docker Desktop 本地自测）
    └── .env.example          # 部署配置样例
```

### 首次部署

```bash
# 1. 云服务器安装 Docker（若已装可跳过）
curl -fsSL https://get.docker.com | sh

# 2. 克隆仓库并一键部署
git clone https://github.com/Venti-XingLanCiJiang-BiLiBiLi/ValuesUnderPressure.git
cd ValuesUnderPressure
./deploy/deploy.sh
```

访问 `http://<服务器IP>:8080`（端口可在 `.env` 的 `VUP_PORT` 修改，默认 8080）。
API 文档在 `http://<服务器IP>:8080/docs`，健康检查在 `/api/health`。

### Windows 本地自测（Docker Desktop）

与 Linux 脚本等价的 Windows 版，适合先在本地验证整套编排：

```powershell
.\deploy\deploy.ps1 -NoPull -Open   # 构建 + 启动 + 健康检查 + 打开浏览器
```

参数：`-NoPull` 跳过 git pull（本地自测常用）、`-NoCache` 强制重新构建、
`-Logs` 部署后跟进日志、`-Open` 部署后自动打开浏览器。
端口同样由 `.env` 的 `VUP_PORT` 控制（默认 8080）。

> 若遇到 PowerShell 执行策略限制（`SecurityError`），用 Bypass 方式运行：
> `powershell -NoProfile -ExecutionPolicy Bypass -File .\deploy\deploy.ps1 -NoPull -Open`

### 日常升级 / 维护

```bash
./deploy/deploy.sh            # 代码更新后重新构建并滚动升级
./deploy/backup.sh            # 手动备份数据库（一致性在线备份 + 压缩）到 backups/
docker compose logs -f        # 查看日志
docker compose down           # 停止（数据仍保留在卷中）
```

Windows（Docker Desktop）本地备份：`\deploy\backup.ps1`（参数 `-BackupsDir` / `-KeepDays`，默认保留 14 天）

定时备份（可选，Linux）：

```bash
crontab -e
0 3 * * * /path/to/ValuesUnderPressure/deploy/backup.sh >> /var/log/vup-backup.log 2>&1
```

> 备份脚本说明：在容器内用 Python `sqlite3` 在线备份 API 生成一致性副本（等价 `sqlite3 .backup`），
> 经 `PRAGMA integrity_check` 完整性校验后 `gzip` 压缩输出 `app_<时间戳>.db.gz`（解压即 SQLite 文件），
> 并按天清理旧备份（默认 14 天，可用环境变量 `BACKUP_DIR` / `KEEP_DAYS` / `DB_PATH` 覆盖）。

> 前端构建默认 `VITE_API_BASE_URL=/api`（同源反代）。仅当采用前后端分离部署时才在 `.env`
> 里覆盖 `VITE_API_BASE_URL=https://你的后端域名/api`，详见 `deploy/.env.example`。

## 测试与校验

```bash
# 题库合并与格式校验（从 v1/questions/ 分桶生成正式题库）
cd question-bank/v1 && python build_questions.py

# 题库加载校验 + 核心流程冒烟测试（backend 目录下）
cd ../backend
python scripts/validate_bank.py    # 退出码 0 通过；1 表示存在被剔除题目
python scripts/smoke_test.py      # 端到端冒烟：创建会话 → 取题 → 提交答案 → 拿结果
```

## 答题修改规则

- 允许修改已经提交的答案（价值观测试不是考试，用户可能误解题意后想更正）。
- 修改**不会**改变当前答题进度：只有首次回答某个问题时进度才 +1。
- 每次修改都会在 `answer_history` 中记录：题目、旧答案、新答案、修改时间。
- 修改后结果会按最新答案重新计算，维度级 `confidence` 同步更新。

相关接口：`POST /api/test/session/{id}/answer`（提交/修改）、`GET /api/test/session/{id}/answers`（当前答案 + 修改历史）。详见 `docs/API.md`。

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
