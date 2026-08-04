# 更新日志（Changelog）

本文件记录取舍之间 (Values Under Pressure, VUP) 项目的变更（题库、后端、前端与部署）。格式遵循 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [1.5.0] - 2026-08-04

### 新增

- **前端隐私政策页与页脚链接**（新增 `frontend/src/views/PrivacyView.vue`；修改 `frontend/src/App.vue`、`frontend/src/router/index.ts`、`frontend/src/api/client.ts`、`frontend/src/types/api.ts`）：
  - 全站页脚（含首页底部）新增「隐私政策」链接，跳转到新路由 `/privacy`；
  - 新增隐私政策页：从后端 `GET /api/meta/privacy` 拉取政策正文（保留期按运行期配置返回），后端不可用时回退内置文案，纯静态托管 / 离线也能正常展示；
  - 政策内容严格依据实际数据实践编写：不收集姓名 / 邮箱等个人身份信息、无第三方追踪与广告；服务端进行中会话保留 3 天、已完成结果保留 15 天后自动删除；结果存档仅存浏览器本地且可随时删除等。

- **后端隐私政策接口**（`backend/app/routers/meta.py`，新增 `backend/tests/test_privacy.py`）：
  - 新增 `GET /api/meta/privacy`：返回结构化隐私政策（版本 / 生效日期 / 保留期 / 章节正文）；
  - 保留期取自运行期环境变量（`SESSION_TTL_DAYS` / `COMPLETED_SESSION_TTL_DAYS`），政策文案与部署配置始终一致；
  - 配套单测覆盖接口结构、保留期正文与实际配置一致、章节标题唯一。

### 变更

- 项目版本号升至 **1.5.0**（`frontend/package.json`、`backend/pyproject.toml`）。

## [1.4.10] - 2026-08-04

### 新增

- **前端结果分享功能（对应 issue #17）**（新增 `frontend/src/utils/shareCard.ts`、`frontend/src/composables/useShareResult.ts`、`frontend/src/views/ResultView.vue`）：
  - 结果页新增「分享结果」按钮：在**浏览器本地**用 Canvas 2D 手绘一张品牌风格的结果卡片（1080×1440 高清 PNG），全程零依赖、不上传任何结果数据；
  - 分享卡片内容与结果页一致：品牌标题 + 10 维度条（按 `|score-50|` 降序、以 50 中线对称展开、高/中/低三档配色，阈值与 `config/theme.ts` 对齐）+ 底部统计（作答进度 / 置信度 / 矛盾数）+ 站点水印；
  - 保存引导：移动端优先走 Web Share API（系统分享面板，可直接「存储图像 / 分享到微信 / 邮件」），桌面端降级为浏览器下载 PNG；用户取消分享面板不视为失败；
  - 卡片本地生成，不含题目与原始回答，仅展示倾向与分值，符合「结果只描述倾向」的产品定位。

### 变更

- 项目版本号升至 **1.4.10**（`frontend/package.json`、`backend/pyproject.toml`）。

## [1.4.9] - 2026-08-04

### 新增

- **前端添加键盘快捷键（对应 issue #19）**（新增 `frontend/src/composables/useKeyboardShortcuts.ts`、`frontend/src/views/TestView.vue`、`frontend/src/style.css`）：
  - 新增 `useKeyboardShortcuts` composable：答题页全局监听 keydown，`Y / →` 选是、`N / ←` 选否、`↑ / Backspace` 上一题、`↓` 下一题；
  - 规则：焦点在输入框不触发、长按连发（`e.repeat`）不触发、`preventDefault` 避免 Backspace 触发浏览器后退；
  - `TestView` 接入快捷键并新增视觉提示（`kbd` 键帽样式，`Y/N/↑/↓` 提示条，对读屏隐藏）。

### 变更

- **前端可访问性（A11y）增强（对应 issue #22）**（`frontend/src/views/TestView.vue`、`frontend/src/components/ProgressBar.vue`）：
  - 答题主区加 `role="main"` + `aria-label`；
  - 进度条（`ProgressBar`）加 `role="progressbar"` + `aria-valuenow/aria-valuemax/aria-label`，读屏可感知当前进度；
  - 题目卡加 `aria-live="polite"` + `aria-atomic="true"`，切题时读屏自动播报；
  - 作答按钮组加 `role="group"` + `aria-label`，Y/N 按钮加 `aria-label` + `aria-pressed`（反映已选状态）；
  - 导航区改为 `<nav aria-label="题目导航">`，上一题/下一题按钮补 `aria-label`。
- 项目版本号升至 **1.4.9**（`frontend/package.json`、`backend/pyproject.toml`）。

## [1.4.8] - 2026-08-04

### 重构

- **前端 Store 模块化拆分（对应 issue #18）**（`frontend/src/stores/`）：
  - `stores/test.ts` 由「单一大 store」重构为**组合门面**，具体状态与请求逻辑下沉到四个单一职责 store：`session.ts`（会话元数据：`sessionId` / `total` / `status`）、`progress.ts`（题目进度与导航：当前题 / 浏览位置 / 已显示缓存 / 回退前进）、`answers.ts`（答案与修改历史）、`result.ts`（结果获取、缓存与自动存档）；
  - `test.ts` 仅保留编排（创建会话→取题→提交→取结果），对外 API 与拆分前完全一致，视图层无需改动，各子 store 可独立测试。

### 新增

- **前端错误边界与重试机制（对应 issue #20）**（`frontend/src/api/client.ts`、`frontend/src/stores/test.ts`、新增 `frontend/src/components/ErrorBoundary.vue`、`frontend/src/App.vue`）：
  - `api/client.ts` 新增 `requestWithRetry()`：带指数退避（1s→2s→4s）的请求重试，**仅对网络层错误（超时 / 断连 / 无响应，`ApiError.status === 0`）重试**，业务错误（4xx/5xx）不重试；所有 API 方法接入（写操作 `submitAnswer` 重试 2 次）；
  - `test.ts` 加载状态由单个 `loading` boolean 细化为 `loadingState`（`idle / creating / fetching / submitting / result`），新增语义化 `isLoading`，旧 `loading` 保留兼容；
  - 新增全局错误边界 `ErrorBoundary.vue`（`onErrorCaptured`），在 `App.vue` 包裹路由视图，后代组件异常不再整页白屏，并提供「重试」按钮。

### 变更

- **前端构建优化（对应 issue #23）**（`frontend/vite.config.ts`、`frontend/nginx.conf`）：
  - `vite.config.ts`：`manualChunks` 增加 `vendor: ['axios']`，第三方依赖不再全部打入主包；开启 `reportCompressedSize` 输出 gzip 体积；
  - `nginx.conf`：gzip 增加 `gzip_comp_level 6` / `gzip_buffers`，并补充 `text/xml` / `application/xml+rss` 等 MIME 类型。
- 项目版本号升至 **1.4.8**（`frontend/package.json`、`backend/pyproject.toml`）。

## [1.4.7] - 2026-08-04

### 新增

- **Session 过期与数据清理机制（对应 issue #10）**（`backend/app/db.py`、`backend/app/main.py`、`backend/tests/test_cleanup.py`）：
  - `test_sessions` 新增 `expires_at` 字段（UTC ISO-8601）及索引 `idx_sessions_expires` / `idx_sessions_status`；`_migrate` 为旧库自动补列并回填历史行（`created_at + TTL`）；
  - `create_session` 默认写入 `now + SESSION_TTL_DAYS` 天（默认 3）；`mark_completed` 完成时延长到 `now + COMPLETED_SESSION_TTL_DAYS` 天（默认 15，已完成结果长期保留）；
  - 新增 `cleanup_expired_sessions()`：删除过期 session 及其关联数据（`answers` / `results` / `answer_history`，因无外键级联需逐表删），返回删除条数；
  - `main.py` lifespan 启动后台定期清理任务 `_periodic_cleanup()`：启动即清理一次，之后每 `CLEANUP_INTERVAL_HOURS`（默认 3）小时清理，随应用关闭取消，单次异常不中断循环；
  - 过期策略/周期均支持环境变量覆盖（`SESSION_TTL_DAYS` / `COMPLETED_SESSION_TTL_DAYS` / `CLEANUP_INTERVAL_HOURS`）。

### 变更

- 项目版本号升至 **1.4.7**（`frontend/package.json`、`backend/pyproject.toml`）。

### 文档

- `docs/DatabaseSchema.md`：`test_sessions` 表补充 `expires_at` 字段说明；
- `deploy/.env.example`：补充 Session 过期与清理的可选配置项说明。

## [1.4.6] - 2026-08-04

### 变更

- **数据库备份可靠性提升（对应 issue #12）**（`deploy/backup.sh`、新增 `deploy/backup.ps1`、`.gitignore`）：
  - `backup.sh` 由「直接拷贝容器内 DB 文件」改为**一致性在线备份**：在容器内用 Python `sqlite3` 在线备份 API（等价 `sqlite3 .backup`）备份 → `PRAGMA integrity_check` 完整性校验（失败删除临时文件并报错退出）→ `gzip` 压缩，再经 `docker cp` 取出；
  - 备份产物改为 `app_<时间戳>.db.gz`（解压即 SQLite 文件），宿主机无需额外安装 `sqlite3` / `gzip`；
  - 保留策略由「保留最近 14 份」改为**按天清理（默认 14 天）**，支持环境变量 `BACKUP_DIR` / `KEEP_DAYS` / `DB_PATH` 覆盖；
  - 新增 Windows 版 `deploy/backup.ps1`（与 `backup.sh` 逻辑一致，支持 `-BackupsDir` / `-KeepDays` 参数）；
  - `.gitignore` 新增忽略 `backups/` 备份产物。
- 项目版本号升至 **1.4.6**（`frontend/package.json`、`backend/pyproject.toml`）。

### 文档

- `README.md`：更新备份相关说明——目录树与维护章节补充 Windows 版 `backup.ps1`，备份脚本描述改为「一致性在线备份 + 压缩 + 按天保留 14 天」。

## [1.4.5] - 2026-08-04

### 重构

- **后端路由模块化拆分（对应 issue #15）**（`backend/app/main.py`、新增 `backend/app/bank_state.py`、`backend/app/routers/`）：
  - `main.py` 瘦身为入口（日志初始化 / lifespan / CORS / 路由挂载），业务路由按域拆分到 `app/routers/`：`meta.py`（健康检查 / 维度元数据）、`admin.py`（题库热更新）、`sessions.py`（测试流程）；
  - 共享题库实例状态抽到 `app/bank_state.py`（`get_bank()` / `set_bank()`），供各路由复用并支持热更新替换；
  - `main.py` 保留 re-export（`get_answers` / `get_result` / `submit_answer` / `reload_bank`）以兼容既有测试导入路径。

### 新增

- **后端数据库异步化（对应 issue #8）**（`backend/app/db.py`、`backend/app/routers/sessions.py`、`backend/scripts/smoke_test.py`、`backend/tests/`）：
  - 持久化层由同步 `sqlite3` 迁移到 `aiosqlite`，全部 db 函数改为 `async def`，沿用「每函数一次连接」短连接模式，由事件循环串行调度，规避 SQLite 并发写锁竞争；
  - 测试流程路由全部改为 `async def` 并 `await` 数据库调用；`smoke_test.py` 以 `asyncio.run` 驱动；
  - 测试适配：`pytest.ini` 启用 `asyncio_mode = auto`，`conftest.py` 与 `test_main.py` 异步化。
- **API 限流与防滥用（对应 issue #9）**（新增 `backend/app/rate_limit.py`、`backend/app/main.py`、`backend/app/routers/*`、`frontend/nginx.conf`、`backend/requirements.txt`）：
  - 集成 slowapi（内存存储），按客户端真实 IP 限流；限流键优先取 Nginx 注入的 `X-Real-IP`，回退 `X-Forwarded-For` / `client.host`（避免反代下所有用户共用一个限流桶）；
  - 限流阈值：`POST /api/test/session` 10 次/分钟、`POST /api/test/session/{id}/answer` 60 次/分钟、`GET /api/health` 100 次/分钟、只读接口 120 次/分钟、`POST /api/admin/reload-bank` 10 次/分钟（叠加 token 鉴权）；
  - 超限返回 HTTP 429（slowapi 默认 `_rate_limit_exceeded_handler`）；
  - Nginx 增加请求体大小限制 `client_max_body_size 1M`。

### 变更

- 项目版本号升至 **1.4.5**（`frontend/package.json`、`backend/pyproject.toml`）。

### 文档

- `docs/API.md`：新增「限流（Rate Limiting）」说明（阈值与 429 行为）；
- `backend/README.md`：补充 API 限流说明。

## [1.4.4] - 2026-08-04

### 新增

- **结构化日志与监控（对应 issue #24）**（`backend/app/main.py`、`backend/requirements.txt`）：
  - 新增 JSON 结构化日志：设置 `JSON_LOGS=1` 时经 `python-json-logger`（`JsonFormatter`）输出 JSON 格式日志，便于 ELK / 集中日志采集；未开启或依赖缺失时回退为纯文本格式；
  - 日志初始化收敛到 `init_logging()`，在应用 `lifespan` 启动时统一配置 handler 并跨热重载去重；模块级 logger 先于 lifespan 定义，避免 `reload_bank` 等被直接调用时报 `NameError`。
- **CORS 生产环境配置收紧（对应 issue #11）**（`backend/app/main.py`、`docker-compose.yml`、`deploy/.env.example`）：
  - CORS 来源改为环境驱动：`CORS_ALLOWED_ORIGINS`（逗号分隔）显式配置；未配置时非生产环境（`ENV != production`）默认放开 `*`，生产环境默认严格（空列表）并记录 warning；
  - 容器间服务互访通常不带 `Origin` 请求头，不受 CORSMiddleware 限制，Docker 内部互访不受影响。

### 变更

- **部署脚本生产检查**（`deploy/deploy.sh`、`deploy/deploy.ps1`）：检测到 `ENV/APP_ENV=production` 且 `CORS_ALLOWED_ORIGINS` 或 `ADMIN_TOKEN` 未设置时输出警告，提示可能影响可用性与安全性。
- **部署配置变量**（`docker-compose.yml`、`deploy/.env.example`）：后端服务新增 `ENV`（与 `APP_ENV` 同步）、`CORS_ALLOWED_ORIGINS`、`JSON_LOGS`、`ADMIN_TOKEN` 环境变量，生产部署可按需配置。
- **后端 CI 冒烟流水线**（新增 `.github/workflows/backend-smoke.yml`）：push / pull_request 命中 `backend/**` 时安装依赖（含 pytest）并运行完整后端测试套件。
- 项目版本号升至 **1.4.4**（`frontend/package.json`、`backend/pyproject.toml`）。

### 修复

- **`backend/app/main.py` 代码规范修复**（本地复现 CI 时发现并修正）：修复 ruff 告警——import 块排序（I001）、移除废弃且未使用的 `typing.List`（UP035 / F401）、`setattr` 常量属性改为直接赋值（B010）、导入块与注释之间补空行；修复后 ruff 与 mypy 均通过。

## [1.4.3] - 2026-08-04

### 新增

- **题库版本 manifest 机制**（`backend/app/manifest.py`、`backend/scripts/generate_manifest.py`）：
  - 每个题库版本目录新增 `manifest.json`，记录 `schema_version` / `bank_version` / `questions_file` / `dimensions_file` / `questions_sha256` / `dimensions_sha256`，确保 `questions.json` 与 `dimensions.json` 永远属于同一题库版本，避免「题库版本与维度定义不匹配」导致测评结果错误；
  - 校验项：文件存在 / `schema_version` 一致 / 文件名引用 / `questions.json` 与 `dimensions.json` 的 sha256 校验，失败抛 `ManifestError`（含修复建议）；
  - 新增生成脚本 `scripts/generate_manifest.py`（自动计算 sha256，默认处理 `QUESTION_BANK_VERSION` 指向的版本目录）；`question-bank/v1/` 与 `question-bank/templates/` 均已生成 `manifest.json`。
- **生产环境维度元数据一致性保护**（`backend/app/dimensions.py`）：`APP_ENV=production|prod` 下 `dimensions.json` **缺失**（`FileNotFoundError`）或**损坏**（JSON 非法/结构不符，`RuntimeError`）时禁止回退内置默认，直接抛错（含当前题库版本、缺失/损坏文件路径与修复建议）；开发环境保持回退行为不变。
- **manifest 接入运行时加载**（`backend/app/question_bank.py`）：生产环境加载版本目录题库（`load_bucket_bank`）前强制 `validate_manifest`，失败即拒绝加载，覆盖启动（`get_bank`）与热更新（`/api/admin/reload-bank`）两条路径；自定义 `QUESTION_BANK_PATH` 与开发环境不强制，保持测试与回退便利。

### 变更

- **production 判定统一收敛**：`APP_ENV=production|prod` 判定从 `question_bank.py` 抽到共享模块 `backend/app/bank_paths.py` 的 `is_production()`（`question_bank` 保留 `_is_production` 别名兼容），`dimensions` 与 `question_bank` 共用同一判定来源，消除重复配置。
- **`scripts/validate_bank.py` 默认优先验证 manifest**：先校验版本目录 `manifest.json`（缺失输出明确错误并返回非零退出码），再全量校验 manifest 引用的 `questions.json`；传单个 `questions.json` 文件仍走旧行为。
- **`build_questions.py` 联动生成 manifest**（`question-bank/v1/`、`question-bank/templates/`）：生成 `questions.json` 后自动产出 `manifest.json`（复用 `app.manifest.build_manifest` 唯一实现），保证「改了题库不会忘更新 manifest」。
- **`build_manifest` 收敛到核心模块**：从 `scripts/generate_manifest.py` 移至 `backend/app/manifest.py`，供生成脚本与题库构建脚本复用。
- 项目版本号升至 **1.4.3**（`frontend/package.json`、`backend/pyproject.toml`）。

### 文档

- `docs/DataValidation.md`：新增第 6 节「题库版本一致性校验（manifest.json）」；
- `docs/DimensionSystem.md`：补充维度元数据在生产环境缺失/损坏时禁止回退的行为；
- `docs/QuestionBankSchema.md`：新增「题库版本清单（manifest.json）」结构与字段说明；
- `backend/README.md`：更新生产/开发回退行为、维度元数据同源与 manifest 运行时校验说明；
- `question-bank/question_bank_readme.md`：补充 `manifest.json` 目录结构、文件表与维护流程。

## [1.4.2] - 2026-08-04

### 新增

- **前后端 CI/CD 流水线**（`.github/workflows/`，对应 issue #13）：
  - 新增 `backend-ci.yml`：push / pull_request 命中 `backend/**`、`question-bank/**` 时自动执行 ruff 代码检查、mypy 类型检查、bandit 安全扫描、题库校验（`scripts/validate_bank.py`）、pytest 单元测试与冒烟测试（`scripts/smoke_test.py`）；bandit 报告（`bandit-report.json`）作为 artifact 上传，`|| true` 不阻断合并，供人工查看；
  - 新增 `frontend-ci.yml`：命中 `frontend/**` 时执行 `vue-tsc` 类型检查与 `vite build`；修复 `cache-dependency-path`（锁文件在 `frontend/` 子目录，此前缓存不生效），Node 版本统一为 24（与部署工作流一致）。

### 变更

- **后端代码质量配置**（新增 `backend/pyproject.toml`）：统一管理 ruff / mypy 规则，保证本地与 CI 行为一致；`per-file-ignores` 豁免业务上有意为之的写法（`db.py` 的 `DTZ005` 本地时间、`dimensions.py` 的 `TRY004` / `PLW0602`、`main.py` 的 `BLE001` 兜底、测试的 `C408`）。
- **校验工具链锁版本**（新增 `backend/requirements-dev.txt`）：锁定 `pytest==9.1.1` / `ruff==0.16.1` / `mypy==2.3.0` / `bandit==1.9.4`，CI 改用 `pip install -r requirements-dev.txt`，避免规则集随最新版漂移。
- **`scripts/validate_bank.py` 改用非弃用校验路径**：复用 `question_bank._validate_raw` / `_to_question` 自实现全量校验，不再调用已弃用的 `load_question_bank` / `QuestionBank`；兼容 API 保留，其测试（`tests/test_question_bank.py`）加 `pytestmark` 抑制 `DeprecationWarning`；默认校验路径改为 `question-bank/<版本>/questions.json`。
- **`scripts/smoke_test.py` 使用临时数据库**：通过 `APERSONALITYTEST_DB_PATH` 指向系统临时目录并清理残留，不再在仓库内生成 `app/data/app.db`。
- 项目版本号升至 **1.4.2**（`frontend/package.json`、`backend/pyproject.toml`）。

### 修复

- 修复 ruff 检查告警：删除 `scoring.py` 未使用变量 `by_id`（F841）；`selection.py` 手写循环改列表推导式（PERF402）；`test_main.py` 的 `.items()` 改 `.values()`（PERF102）；`db.py` 的 `datetime.timezone.utc` 改用 `datetime.UTC` 别名（UP017）。
- 修复 mypy 类型告警：`question_bank.py` 的 `seen_ids` 补充类型注解（`set[str]`）。

## [1.4.1] - 2026-08-04

### 变更

- **`questions.json` 标记 `@deprecated`（保留兼容）**：
  - 前后端正常运行已不依赖版本目录内的 `questions.json`（抽题走分桶索引 `questions.index.json`），将其标记为**合并产物/构建快照**，仅用于全量校验（`scripts/validate_bank.py`）、分桶索引缺失时的开发回退；
  - 后端旧接口 `load_question_bank` / `QuestionBank` 标注 `@deprecated`，调用时发出 `DeprecationWarning`（功能保留：`validate_bank.py`、`test_question_bank.py` 仍可用）；`load_bucket_bank()` 的 `questions.json` 回退分支标注 deprecated 注释；
  - 文档（`question-bank/question_bank_readme.md`、`backend/README.md`、根 `README.md`）同步标注 `@deprecated` 与「非抽题运行时数据源」。
- **前端 health 类型修正**（`frontend/src/types/api.ts`）：`HealthResponse` 由旧字段 `question_bank_source` / `invalid_questions` 改为与后端一致的 `question_bank_version` / `groups` / `active_questions`。
- **修复 Pylance 类型告警**（`backend/app/question_bank.py`）：`metadata.version` 判空后比较，消除 "None 不支持 <" 编译告警。

- **前端：优化作答按钮与退出确认交互**：
  - 调整 `Y/N` 作答按钮在浅色与深色模式下的配色与阴影，降低饱和度和高亮感以避免视觉暗示；相关样式位于 `frontend/src/style.css`（调整 `.btn-y` / `.btn-n`），并对深色模式进一步降低不透明度与阴影强度以减轻视觉冲击；
  - 将页面中使用的系统 `confirm()` 替换为可复用的应用内确认对话组件 `frontend/src/components/ConfirmDialog.vue`，并在 `frontend/src/views/TestView.vue` 中使用该组件以统一样式与交互；
  - 这些改动旨在提升可访问性与视觉中性，文件变更包括：`frontend/src/style.css`、`frontend/src/views/TestView.vue`、`frontend/src/components/ConfirmDialog.vue`。

## [1.4.0] - 2026-08-04

### 变更

- **后端抽题改为桶驱动，依赖分桶索引**（`backend/app/selection.py`、`backend/app/question_bank.py`、`backend/app/main.py`）：
  - 新增 `BucketBank`：基于 `questions.index.json`（分桶索引）的懒加载题库，按需读取桶文件，不再全量加载 `questions.json`；新增 `load_bucket_bank()` 作为抽题主数据源；
  - 抽题算法改为「先抽桶、再在桶内随机取题」：某组（m 桶、d 题）抽 n 题时，先抽 `k = min(n, m)` 桶，候选不足 n 题时重复抽桶补充，桶内取题不重复；组内题数不足（d < n）按 fallback 补齐（维度组 → must → experimental）；整卷最后校验重复题并按 fallback 重抽；
  - **放弃难度分层抽取**（移除 `_split_quota_by_difficulty` / `DIFFICULTY_ORDER` 及对应测试）；
  - 组卷按分桶索引的维度组分配配额（默认 50 题 = must 5 + experimental 1 + 常规 10 维度 44，随机 4 维抽 5 题、6 维抽 4 题）。
- **题库版本控制**（`backend/Dockerfile`、`docker-compose.yml`、`deploy/.env.example`）：
  - 新增环境变量 `QUESTION_BANK_VERSION` 控制题库版本（默认 `v1`，对应 `question-bank/<版本>/` 目录）；Dockerfile 改为 COPY `question-bank/v1` 到镜像，生产由版本键决定加载哪个版本的分桶索引；
  - `docker-compose.yml` / `deploy/.env.example` 同步增加 `QUESTION_BANK_VERSION` 配置。
- **文档同步**：`docs/QuestionSelection.md`（桶驱动抽题算法，移除难度分层）、`backend/README.md`、仓库根 `README.md`。

## [1.3.0] - 2026-08-04

### 变更

- **题库分文件管理**（`question-bank/`，对应 issue #21）：将单文件 254KB 的 `questions.json`（500 题）按主维度拆分到分桶目录（每桶 4 题）：
  - 常规 9 维度每目录 10 个桶文件（`{ABBR}_Bnk{权重}.json`，每桶 4 题）；`freedom` 每权重桶 8 题，拆 2 个 4 题桶文件（`FD_Bnk{权重}_1/2.json`）；
  - `must` 40 题按 `Q00441~Q00480` 顺序每 4 题一桶（`Must_Bnk01~10.json`，对应后端 `MUST_BUCKET_SIZE=4` 抽样）；`experimental` 20 题不分桶（`Exp_Bnk01.json`）；
  - 新增 `questions.index.json`：分桶索引（结构记录），记录各组题数、桶数、每桶数量与文件位置；
  - 减少版本控制冲突、便于运营按桶维护与后续按需加载（先加载 `must` 再懒加载常规题）；
  - 历史批次目录 `question-bank/drafts/` 标记废弃（保留本地，不入库）。
- **题库版本文件夹管理**（`question-bank/`）：将题库改为按版本目录组织：
  - 新建 `question-bank/v1/` 作为题库版本 v1，将 `questions/`（分桶源文件）、`build_questions.py`、`questions.json`、`questions.index.json` 全部移入 `v1/`；构建脚本基于 `__file__` 定位，移动后路径自动正确，`v1/questions.json` 内容与格式不变；
  - 新建范例题库框架 `question-bank/templates/`（与版本目录同构）：`templates/questions/` 分层分桶源文件（2 维度 x 2 桶 x 2 题，全为占位数据）、`templates/build_questions.py`（模板构建脚本，可调整 `DIMENSIONS` / `EXPECTED_PER_BUCKET` / `ID_PREFIX` 等常量）、`templates/questions.json` 与 `templates/questions.index.json`（合并产物 + 分桶索引）；可复制为新版本骨架；
  - 前端/后端读取 `question-bank/questions.json` 的路径更新属后续任务（本版仅完成题库结构改造与文档）。

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
