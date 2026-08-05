# 取舍之间 · 价值观压力测试 — Frontend

> **取舍之间** (Values Under Pressure，简称 VUP)
> 基于极端价值冲突场景的 Y/N 二选一测试，10 个核心维度，结果只描述倾向、允许矛盾。

本目录为 **B 站 Toy 适配版**前端：组卷、评分、结果生成全部在浏览器本地完成（见 `src/engine/`），
无后端服务、无网络请求。题库随包内嵌（`question-bank/v1/` 的三个 JSON 文件在构建时打入 bundle）。

**强调**：本测试**不是** MBTI / 性格分类。结果只描述价值倾向，且明确允许矛盾。

## 技术栈

| 类别 | 选型 |
|---|---|
| 构建 | Vite 5 |
| 框架 | Vue 3 + Composition API |
| 语言 | TypeScript |
| 样式 | TailwindCSS 3 |
| 状态 | Pinia |
| 路由 | Vue Router 4（hash 模式，兼容静态托管） |
| 测试 | Vitest（引擎 / 组合式函数单元测试） |
| 依赖 HTTP | 无（已移除 axios） |

## 快速开始

```bash
cd frontend
npm install
npm run dev
```

打开 `http://127.0.0.1:5173`——无后端依赖，直接可用。

## 可用脚本

| 命令 | 作用 |
|---|---|
| `npm run dev` | 启动开发服务器（HMR） |
| `npm run test` | Vitest 单元测试 |
| `npm run typecheck` | vue-tsc 类型检查 |
| `npm run build` | 生产构建到 `dist/` |
| `npm run preview` | 预览生产构建 |

## 目录结构

```
frontend/
├── index.html                 # Vite 入口（引入 Toy SDK 脚本）
├── vite.config.ts             # Vite 配置（相对 base，无 /api 代理）
├── tailwind.config.js         # 自定义墨青+暖橘色板
└── src/
    ├── main.ts                # 挂载 Vue + Pinia + Router
    ├── App.vue                # 布局 + 页面切换过渡
    ├── engine/                # 本地组卷引擎（纯 TS，移植自服务器版）
    │   ├── bank.ts            # 题库加载 + 分桶索引校验（import 内嵌 JSON）
    │   ├── rng.ts             # mulberry32 种子随机（对齐原 random.Random 语义）
    │   ├── selection.ts       # 桶驱动随机组卷
    │   ├── scoring.ts         # 评分 + 归一化 + 一致性 + 矛盾分析
    │   ├── session.ts         # 本地会话状态机（localStorage）
    │   └── index.ts           # testApi 兼容层（API 签名对齐原后端接口）
    ├── api/
    │   └── client.ts          # 本地引擎适配器（testApi / ApiError）
    ├── stores/                # test / session / progress / answers / result
    ├── types/
    │   ├── api.ts             # 结果/题目等 TS 类型
    │   └── toy.d.ts           # B 站 Toy SDK 类型声明（window.toy）
    ├── composables/
    │   ├── useToy.ts              # Toy SDK 安全访问（能力检测）
    │   ├── useDimensionMeta.ts    # 维度元数据加载（v1.6：label + 高低分标签/描述）
    │   ├── useToyCloudArchive.ts  # 云端存档（摘要 + 完整结果分块，128 key 上限）
    │   ├── useArchives.ts         # 本地存档（localStorage）
    │   ├── useSessionRestore.ts   # 会话进度恢复
    │   ├── useTheme.ts / useKeyboardShortcuts.ts
    ├── utils/shareCard.ts     # 结果分享卡片 Canvas 渲染（零依赖，条底两端高低分标签）
    ├── components/            # ProgressBar / DimensionBar / ConflictCard / ResultContent / ShareResultModal ...
    └── views/                 # IntroView（含云端存档）/ TestView / ResultView / ArchiveView / PrivacyView
```

## B 站 Toy 适配

- `index.html` 加载 `toy-sdk.js`，运行时经 `useToy.ts` 检测 `window.toy` 能力，全部调用安全降级：
  - **保存到相册**：结果分享弹窗（`ShareResultModal.vue`）优先 `toy.saveImageToAlbum`（base64 ≤ 1.8MB，过大自动 JPEG
    压缩/缩放降级），非 Toy 环境回退 Web Share API / 浏览器下载；
  - **云端存档**：完成测试后自动把结果备份到 B 站云存储（摘要 `latest` + `h<ts>` 双写、完整结果按字节分块存
    `r<ts>_<n>`、按账号隔离、128 key 上限、删除时同步清理 latest 与分块）；首页「云端存档」可
    **查看（复用 ArchiveView，`/archive?cloud=<ts>`）/ 删除**，换设备也能回顾完整结果；
  - 普通浏览器（无 Toy）所有功能自动降级，不影响使用。

## 题库说明

- 正式题库数据：`../question-bank/v1/{questions,questions.index,dimensions}.json`，
  由 `src/engine/bank.ts` 在构建时内嵌；本分支不保留分桶源文件与生成脚本
  （需要更新题库请回到主分支）。
- 引擎算法移植自服务器版 Python 实现（`selection.py` / `scoring.py` / `question_bank.py`），
  移植语义见各模块文件头注释，`docs/` 下有算法设计文档。

## 设计原则

1. **不人格分类**——文案里从不出现"你是 XX 型人"，只用"倾向"。
2. **矛盾是常态**——`result.conflicts` 不是错误而是洞察，UI 给到独立板块。
3. **可逆可重测**——任何阶段都允许退出，不强制注册。
4. **隐私优先**——原始答案只存本机；云端仅备份结果（摘要 + 完整结果分块），按账号隔离可删除。

## 浏览器支持

现代浏览器（Chrome 100+ / Edge 100+ / Firefox 100+ / Safari 15+）。
