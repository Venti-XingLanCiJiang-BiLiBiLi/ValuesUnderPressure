# 取舍之间 · 价值观压力测试 — Frontend

> **取舍之间** (Values Under Pressure，简称 VUP)
> 基于极端价值冲突场景的 Y/N 二选一测试，10 个核心维度，结果只描述倾向、允许矛盾。

## 这是什么

这是 `ValuesUnderPressure` 仓库的**前端实现**——后端 FastAPI 服务已经就绪（见 `../backend/`），
本目录提供面向用户的浏览器端：开屏介绍 → 逐题作答 → 维度结果 + 矛盾分析。

**强调**：本测试**不是** MBTI / 性格分类。结果只描述价值倾向，且明确允许矛盾——
这一点是产品定位的核心，前后端、文档、UI 措辞都按此统一。

## 技术栈

| 类别 | 选型 | 理由 |
|---|---|---|
| 构建 | Vite 5 | 启动快，HMR 顺滑 |
| 框架 | Vue 3 + Composition API | 题目切换的过渡动画写起来更优雅 |
| 语言 | TypeScript | 锁死后端 API 响应类型 |
| 样式 | TailwindCSS 3 | 快速出精致 UI |
| 状态 | Pinia | 轻量、TS 友好 |
| 路由 | Vue Router 4 | 标准选择 |
| HTTP | Axios | 拦截器统一错误处理 |

## 快速开始

### 1. 启动后端

```bash
cd ../backend
# 第一次跑需要装依赖
# Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

确认后端在 `http://127.0.0.1:8000` 跑起来，并能在 `http://127.0.0.1:8000/api/health` 看到
`{"status":"ok", ...}`。

### 2. 启动前端

```bash
cd frontend
npm install
npm run dev
```

打开 `http://127.0.0.1:5173`。

> Vite 在 `vite.config.ts` 里已经把 `/api` 代理到 `http://127.0.0.1:8000`，
> 所以前端代码里统一用 `/api` 即可，不用关心后端端口。

### 3. 验证端到端

```bash
# 后端仓库根目录另开一个 shell
python ../backend/scripts/smoke_test.py
```

会跑通：创建会话 → 取题 → 提交答案 → 拿结果 的完整链路。

## 可用脚本

| 命令 | 作用 |
|---|---|
| `npm run dev` | 启动开发服务器（HMR） |
| `npm run build` | 类型检查 + 生产构建 |
| `npm run preview` | 预览生产构建 |
| `npm run typecheck` | 仅跑 vue-tsc 类型检查 |

## 目录结构

```
frontend/
├── index.html                 # Vite 入口
├── vite.config.ts             # Vite 配置（含 /api 代理）
├── tailwind.config.js         # 自定义墨青+暖橘色板
├── tsconfig.json              # 路径别名 @ -> src
└── src/
    ├── main.ts                # 挂载 Vue + Pinia + Router
    ├── App.vue                # 布局（header / main / footer）+ 页面切换过渡
    ├── style.css              # Tailwind 三段式 + 组件类
    ├── env.d.ts
    ├── api/
    │   └── client.ts          # Axios 实例 + testApi（严格对齐后端 Pydantic schema，带网络重试）
    ├── stores/
    │   ├── test.ts            # 组合门面：编排 创建会话→取题→提交→结果（对外 API 不变）
    │   ├── session.ts         # 会话元数据（sessionId / total / status）
    │   ├── progress.ts        # 题目进度与导航（当前题 / 已显示缓存 / 回退前进）
    │   ├── answers.ts         # 答案与修改历史（answer_history）
    │   └── result.ts          # 结果获取、缓存与自动存档
    ├── router/
    │   └── index.ts           # 路由：/ (开屏) → /test → /result → /archive/:sessionId
    ├── types/
    │   └── api.ts             # 与后端 schemas.py 1:1 对应的 TS 类型
    ├── composables/
    │   ├── useSessionRestore.ts    # 会话进度恢复（sessionStorage）
    │   ├── useArchives.ts          # 本地存档（localStorage，答完自动保存）
    │   ├── useTheme.ts             # 主题切换
    │   └── useKeyboardShortcuts.ts # 答题页键盘快捷键（Y/N、↑/Backspace、↓）
    ├── components/
    │   ├── ProgressBar.vue    # 进度条
    │   ├── DimensionBar.vue   # 单维度条 + 一致性标记
    │   ├── ConflictCard.vue   # 矛盾组合提示
    │   ├── ResultContent.vue  # 结果内容渲染（结果页/存档页复用）
    │   ├── LoadingState.vue   # 加载态
    │   └── ErrorBoundary.vue  # 全局错误边界（onErrorCaptured + 重试按钮）
    └── views/
        ├── IntroView.vue      # 开屏 + 题量选择 + 存档列表
        ├── TestView.vue       # 逐题 Y/N + 过渡动画
        ├── ResultView.vue     # 维度画像 + 矛盾分析
        ├── ArchiveView.vue    # 本地存档查看 / 删除
        └── NotFoundView.vue
```

## 与后端 API 的对接

前端通过 `src/api/client.ts` 里的 `testApi` 对象与后端 4 个接口通信：

| 接口 | 前端调用 | 说明 |
|---|---|---|
| `POST /api/test/session` | `testApi.createSession({ length, dimensions })` | 创建会话，固化本次试卷 |
| `GET /api/test/session/{id}/question` | `testApi.nextQuestion(id)` | 拿下一题（已答完会 409） |
| `POST /api/test/session/{id}/answer` | `testApi.submitAnswer(id, { question_id, answer, duration })` | 提交 Y/N，附带思考时长 |
| `GET /api/test/session/{id}/result` | `testApi.getResult(id)` | 拿结果（包含 `dimensions` / `conflicts` / `uncertain_dimensions`） |

完整接口约定见 `../docs/API.md`，后端实现见 `../backend/app/main.py`。

## 设计原则（与产品定位一致）

1. **不人格分类**——文案里从不出现"你是 XX 型人"，只用"倾向"。
2. **矛盾是常态**——`result.conflicts` 不是错误而是洞察，UI 给到独立板块。
3. **可逆可重测**——任何阶段都允许退出，不强制注册。
4. **前后端对齐**——TS 类型与后端 Pydantic 1:1 映射，避免字段漂移。

## 部署（GitHub Pages）

仓库已内置 CI 工作流 `.github/workflows/deploy-frontend.yml`：push 到 `main`
（且改动涉及 `frontend/**` 或 workflow 本身）时自动构建 `frontend/dist` 并部署到
GitHub Pages，也可手动触发。

### 首次部署步骤

1. **开启 GitHub Pages（源设为 GitHub Actions）**：仓库
   Settings → Pages → Source 选 `GitHub Actions`（只需设置一次）。
2. **提交并推送**：把 `frontend/` 与 `.github/workflows/` 提交到 `main` 分支。
3. 工作流自动构建并部署，访问地址：
   `https://<user>.github.io/ValuesUnderPressure/`
4. 也可以手动触发：Actions → Deploy Frontend to GitHub Pages → Run workflow。

### 后端 API 配置（重要）

GitHub Pages 是**纯静态托管，不能运行 FastAPI 后端**，因此有两种模式：

- **仅前端预览**：不配置 `VITE_API_BASE_URL`（默认 `/api`）。站点能打开，但开始
  测试时会因连不上后端而报错。
- **完整可用**：把后端（`backend/`）部署到 Render / Railway / Fly.io / VPS 等，
  然后在 Settings → Secrets and variables → Actions → Variables 新建变量
  `VITE_API_BASE_URL`，值设为后端公网地址（如 `https://api.example.com/api`）。
  后端 CORS 已开启 `allow_origins=["*"]`，跨域调用无需额外处理。

### 路由说明

前端使用 **hash 路由**（`#/test`、`#/result`），兼容 GitHub Pages 的静态托管——
history 模式在刷新/直达子路由时会 404。

### 本地构建预览

```bash
npm run build        # 类型检查 + 生产构建到 dist/
npm run preview      # 本地预览生产构建
```

## 浏览器支持

现代浏览器（Chrome 100+ / Edge 100+ / Firefox 100+ / Safari 15+）。未做 IE / 旧版兼容。
