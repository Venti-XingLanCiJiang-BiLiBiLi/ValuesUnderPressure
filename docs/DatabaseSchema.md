# 数据库结构设计

## 1. 设计目标

存储题库、测试记录、答案和分析结果。

## 2. 核心表

## questions

|字段|类型|说明|
|-|-|-|
|id|string|题目ID|
|content|text|问题内容|
|version|int|版本|
|status|string|状态|

## question_weights

|字段|类型|说明|
|-|-|-|
|question_id|string|题目|
|dimension|string|维度|
|yes_weight|int|Y权重|
|no_weight|int|N权重|

## test_sessions

|字段|类型|说明|
|-|-|-|
|id|string|测试ID|
|created_at|datetime|创建时间|
|question_version|string|题库版本|
|expires_at|datetime|过期时间（UTC ISO-8601）。创建时默认 `now + SESSION_TTL_DAYS` 天，完成时延长到 `now + COMPLETED_SESSION_TTL_DAYS` 天；后台任务定期清理已过期 session 及其关联数据（见 `cleanup_expired_sessions`）|

## answers

|字段|类型|说明|
|-|-|-|
|session_id|string|测试ID|
|question_id|string|题目|
|answer|string|Y/N|
|duration|int|答题耗时|

> 允许修改：同一 `(session_id, question_id)` 重复提交时以 `UPDATE` 覆盖最新答案，修改记录写入 `answer_history`。

## answer_history

|字段|类型|说明|
|-|-|-|
|id|int|自增主键|
|session_id|string|测试ID|
|question_id|string|题目|
|old_answer|string|修改前答案|
|new_answer|string|修改后答案|
|changed_at|datetime|修改时间|

## results

|字段|类型|说明|
|-|-|-|
|session_id|string|测试ID|
|dimension|string|维度|
|score|float|得分|
|consistency|float|一致性 (0~1)|
|confidence|float|维度级置信度 (0~1)|

## 3. 版本控制

题目和权重必须保存版本，保证历史测试结果可复现。
