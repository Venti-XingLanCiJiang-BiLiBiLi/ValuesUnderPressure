# 前后端接口设计

## 1. API 目标

定义测试流程中的客户端、服务端交互。

## 2. 测试流程接口

### 创建测试会话

```
POST /api/test/session
```

Response:

```json
{
  "session_id": "xxx",
  "question_count": 50
}
```

---

### 获取下一题

```
GET /api/test/session/{id}/question
```

Response:

```json
{
  "question_id": "Q00001",
  "content": "问题文本",
  "type": "YN",
  "index": 0,
  "total": 50
}
```

已答完全部题目时返回 HTTP 409。

---

### 提交答案

```
POST /api/test/session/{id}/answer
```

Request:

```json
{
  "question_id": "Q00001",
  "answer": "Y",
  "duration": 8
}
```

**答题修改规则**：允许修改已提交的答案（价值观测试不是考试，用户可能误解题意后想更正）。

- 修改不会改变当前答题进度（只有首次回答某个问题时进度才 +1）；
- 每次修改都会写入 `answer_history`（题目、旧答案、新答案、修改时间）；
- 重复提交相同答案不会产生新的历史记录。

Response:

```json
{
  "status": "ok",
  "answered_count": 18,
  "total": 50,
  "completed": false,
  "answer_history": [
    {
      "question_id": "Q00001",
      "old_answer": "Y",
      "new_answer": "N",
      "changed_at": "2026-08-03T12:00:00"
    }
  ]
}
```

---

### 获取当前答案与修改历史

```
GET /api/test/session/{id}/answers
```

Response:

```json
{
  "session_id": "xxx",
  "answers": {
    "Q00001": "N",
    "Q00002": "Y"
  },
  "answer_history": [
    {
      "question_id": "Q00001",
      "old_answer": "Y",
      "new_answer": "N",
      "changed_at": "2026-08-03T12:00:00"
    }
  ]
}
```

---

### 获取结果

```
GET /api/test/session/{id}/result
```

Response:

```json
{
  "session_id": "xxx",
  "completed": true,
  "answered_count": 50,
  "total": 50,
  "dimensions": {
    "privacy": {
      "dimension": "privacy",
      "name": "隐私保护",
      "score": 80,
      "tendency": "隐私保护",
      "description": "...",
      "consistency": 0.85,
      "question_count": 5,
      "confidence": 0.82
    },
    "freedom": {
      "dimension": "freedom",
      "name": "自由需求",
      "score": 90,
      "tendency": "追求自主",
      "description": "...",
      "consistency": 0.9,
      "question_count": 5,
      "confidence": 0.88
    }
  },
  "confidence": 0.85,
  "conflicts": [],
  "uncertain_dimensions": []
}
```

> `dimensions[*].confidence` 为维度级可信度（0~1），综合题目数量、作答一致性、权重覆盖程度；
> 维度题量过少或回答高度矛盾时会自动降低。算法见 `docs/ScoringAlgorithm.md`。

> **未完成时不返回部分结果**：尚未作答全部题目时，本接口返回 HTTP 409，不会输出部分画像
> （归一化与一致性需要完整样本才有效）。客户端应在 `answered_count == total` 后再调用。

## 3. 管理接口

未来支持：

- 题库管理
- 权重调整
- 数据分析
- 版本发布

---

## 4. 限流（Rate Limiting）

后端基于 slowapi 对 API 做按客户端 IP 的限流（内存存储，单实例部署），超限返回 HTTP 429。

| 接口 | 限流 |
|------|------|
| `POST /api/test/session` | 10 次 / 分钟 |
| `POST /api/test/session/{id}/answer` | 60 次 / 分钟 |
| `GET /api/health` | 100 次 / 分钟 |
| `GET /api/dimensions`、`GET /api/test/session/{id}/question`、`/answers`、`/result` | 120 次 / 分钟 |
| `POST /api/admin/reload-bank` | 10 次 / 分钟（叠加 `X-Admin-Token` 鉴权） |

> 客户端 IP 取自 Nginx 反代注入的 `X-Real-IP`（回退 `X-Forwarded-For` / 直连地址）；
> 阈值如需调整，见 `backend/app/routers/` 中各端点上的 `@limiter.limit(...)`。
