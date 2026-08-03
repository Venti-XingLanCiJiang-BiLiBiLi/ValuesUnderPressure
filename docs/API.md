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
  "question_count": 40
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
  "type": "YN"
}
```

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

---

### 获取结果

```
GET /api/test/session/{id}/result
```

Response:

```json
{
  "dimensions": {
    "privacy": 80,
    "freedom": 90
  },
  "confidence": 0.85
}
```

## 3. 管理接口

未来支持：

- 题库管理
- 权重调整
- 数据分析
- 版本发布
