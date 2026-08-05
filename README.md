# 取舍之间 · 价值观压力测试（Values Under Pressure · VUP）

基于**极端价值冲突场景**的价值观压力测试 + 多维人格画像。

通过 Y/N 二选一作答，测量用户在 10 个核心价值维度上的底线与优先级。**不是 MBTI / 人格分类测试**——结果只描述倾向，不做人格定性判断，允许不同情境下出现矛盾。

> 本分支为 **B 站 Toy 适配版**：引擎、题库、结果生成全部在浏览器本地完成，无后端服务。
> 服务器版（FastAPI + SQLite）见主分支。

## 功能特性

- **10 个核心价值维度**：自我保护 🛡️ / 利他 🤝 / 自由 🕊️ / 安全 🔒 / 隐私 👁️ / 财富 💰 / 规则 ⚖️ / 务实 🎯 / 集体 👥 / 长期 🌱
- **Y/N 二选一**：极端两难情境，无正确答案、不评善恶，只记录你的取舍
- **题量可选**：30 / 50 / 70 题（默认 50），支持按维度筛选组卷
- **结果只描述倾向**：10 维度画像 + 矛盾组合分析 + 情境依赖提示，不做人格定性；维度条以 50 中线向两侧展开、颜色区分倾向强度
- **纯前端组卷引擎**：抽题、评分、矛盾分析（移植自服务器版 Python 实现），题库随包内嵌，无任何网络请求
- **可修改答案**：价值观测试不是考试，允许修改已提交的答案，修改记录保留，不影响答题进度
- **维度级置信度**：每个维度除分数外，还给出 0~1 的 `confidence`（综合题量、一致性、权重覆盖）
- **本地存档**：答完自动保存结果到本机（localStorage），首页「我的存档」可随时查看 / 删除历史结果
- **B 站 Toy 适配**：结果卡片一键保存到相册 / 分享；云端存档按 B 站账号隔离（跨设备回顾，最多 128 条）
- **深色 / 浅色主题**、**刷新恢复**（会话与结果页均可在刷新后继续）

## 技术栈

| 项 | 技术 |
| --- | --- |
| 前端 | Vue 3 · TypeScript · Vite · TailwindCSS · Pinia · Vue Router |
| 测试 | Vitest（引擎 / 组合式函数单元测试） |
| 运行环境 | B 站 Toy（`window.toy` SDK）· 普通浏览器（降级可用） |

## 项目结构

```
ValuesUnderPressure/
├── frontend/
│   ├── src/
│   │   ├── engine/          # 本地组卷引擎（题库加载、随机组卷、评分、会话）
│   │   ├── composables/     # 组合式函数（分享/下载、本地存档、Toy 云存档）
│   │   ├── stores/          # Pinia（答题进度、会话、结果）
│   │   └── views/           # 页面（首页 / 答题 / 结果 / 隐私）
│   ├── public/favicon.svg
│   └── index.html           # 引入 Toy SDK 脚本
├── question-bank/v1/        # 正式题库（questions.json / questions.index.json / dimensions.json）
├── docs/                    # 设计文档（测试机制、评分算法、维度定义等）
└── README.md
```

## 快速开始

```bash
cd frontend
npm install
npm run dev
```

打开 http://127.0.0.1:5173（无后端依赖，直接可用）。

```bash
npm run test       # Vitest 单元测试
npm run typecheck  # vue-tsc 类型检查
npm run build      # 产物输出到 frontend/dist/
```

## B 站 Toy 说明

- `index.html` 引入 Toy SDK（`toy-sdk.js`），运行时通过 `window.toy` 能力检测自动启用：
  - **保存到相册**：结果页优先调用 `toy.saveImageToAlbum`（base64 ≤ 1.8MB，过大自动 JPEG 压缩降级），非 Toy 环境回退为 Web Share / 浏览器下载；
  - **云端存档**：完成测试后自动把结果摘要备份到 B 站云存储（`latest` + 历史双写、按账号隔离、128 条上限），首页「云端存档」可查看 / 删除；
  - 非 Toy 环境（普通浏览器）所有能力自动降级，功能不受影响。
- 打包产物为 `frontend/dist/`（相对路径引用，可部署到任意子路径）。

## 隐私

纯前端运行：题目与原始回答只存本机，不上传；云端存档仅备份结果摘要，按 B 站账号隔离，可随时删除。详见应用内「隐私政策」页与 `docs/`。

## 文档索引

| 文档 | 内容 |
| --- | --- |
| `docs/TestDesign.md` | 测试机制与设计原则 |
| `docs/DimensionSystem.md` | 10 个核心价值维度定义 |
| `docs/ScoringAlgorithm.md` | 累加 + 归一化 + 一致性算法 |
| `docs/QuestionSelection.md` | 桶驱动随机组卷算法 |
| `docs/QuestionBankSchema.md` | 题库数据结构 |
| `docs/ResultInterpretation.md` | 结果解读说明 |

## 许可证

[GPL-3.0](./LICENSE)
