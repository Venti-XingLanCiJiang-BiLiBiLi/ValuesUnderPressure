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

## answers

|字段|类型|说明|
|-|-|-|
|session_id|string|测试ID|
|question_id|string|题目|
|answer|string|Y/N|
|duration|int|答题耗时|

## results

|字段|类型|说明|
|-|-|-|
|session_id|string|测试ID|
|dimension|string|维度|
|score|float|得分|

## 3. 版本控制

题目和权重必须保存版本，保证历史测试结果可复现。
