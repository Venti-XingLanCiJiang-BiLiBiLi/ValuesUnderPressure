# -*- coding: utf-8 -*-
"""合并并校验题库批次文件，生成 question-bank/questions.json

用法:
    python build_questions.py

校验项 (对应 docs/DataValidation.md):
  - 总题数 / 每维度题数
  - 每个 (维度, 主权重桶) 的题数 (目标: 10 桶 x 4 题 = 40/维度)
  - id 唯一且连续 (Q00001..Q00400)
  - type 必须为 YN
  - category / difficulty 取值合法
  - 权重范围 -5..5, yes/no 不同时为 0, 同题同维度不重复
  - dimension 必须在合法维度集合内
  - content 非空且无重复
"""

import json
import os
import re
import sys

# 脚本位于 question-bank/tools/ 下，题库根目录是其上一级
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DRAFTS_DIR = os.path.join(ROOT, "drafts")
OUTPUT_PATH = os.path.join(ROOT, "questions.json")

DIMENSIONS = {
    "self_protection", "altruism", "freedom", "security", "privacy",
    "wealth", "rule_orientation", "pragmatism", "collectivism", "long_term",
}
CATEGORIES = {
    "personal_boundary", "privacy", "freedom", "safety", "wealth",
    "morality", "social", "future", "risk", "control",
}
DIFFICULTIES = {"easy", "medium", "hard"}
WEIGHT_BUCKETS = [-5, -4, -3, -2, -1, 1, 2, 3, 4, 5]
EXPECTED_TOTAL = 400
EXPECTED_PER_DIM = 40
EXPECTED_PER_BUCKET = 4

BATCH_ORDER = [
    "batch_01_self_protection.json",
    "batch_02_altruism.json",
    "batch_03_freedom.json",
    "batch_04_security.json",
    "batch_05_privacy.json",
    "batch_06_wealth.json",
    "batch_07_rule_orientation.json",
    "batch_08_pragmatism.json",
    "batch_09_collectivism.json",
    "batch_10_long_term.json",
]

errors = []


def error(msg):
    errors.append(msg)


def load_batches():
    questions = []
    for fname in BATCH_ORDER:
        path = os.path.join(DRAFTS_DIR, fname)
        if not os.path.exists(path):
            error(f"缺少批次文件: {fname}")
            continue
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            error(f"{fname}: 顶层不是数组")
            continue
        for q in data:
            q["_batch"] = fname
        questions.extend(data)
    return questions


def validate_question(q):
    qid = q.get("id", "<no-id>")
    where = f"{q.get('_batch','?')} / {qid}"

    # content
    content = q.get("content", "")
    if not isinstance(content, str) or not content.strip():
        error(f"{where}: content 为空")

    # type
    if q.get("type") != "YN":
        error(f"{where}: type 必须为 YN, 实际为 {q.get('type')!r}")

    # category
    if q.get("category") not in CATEGORIES:
        error(f"{where}: category 非法 -> {q.get('category')!r}")

    # difficulty
    if q.get("difficulty") not in DIFFICULTIES:
        error(f"{where}: difficulty 非法 -> {q.get('difficulty')!r}")

    # tags
    tags = q.get("tags", [])
    if not isinstance(tags, list) or not tags:
        error(f"{where}: tags 为空")

    # weights
    weights = q.get("weights", [])
    if not isinstance(weights, list) or not weights:
        error(f"{where}: weights 为空")
        return None
    seen_dims = set()
    for w in weights:
        dim = w.get("dimension")
        yes, no = w.get("yes"), w.get("no")
        if dim not in DIMENSIONS:
            error(f"{where}: dimension 非法 -> {dim!r}")
        if dim in seen_dims:
            error(f"{where}: 同题重复维度 {dim}")
        seen_dims.add(dim)
        if not (-5 <= yes <= 5 and isinstance(yes, int)):
            error(f"{where}: yes 超出范围 -> {yes!r}")
        if not (-5 <= no <= 5 and isinstance(no, int)):
            error(f"{where}: no 超出范围 -> {no!r}")
        if yes == 0 and no == 0:
            error(f"{where}: {dim} 的 yes/no 同时为 0")

    # 主维度 = weights[0]，主权重桶 = weights[0].yes
    primary = weights[0].get("dimension")
    bucket = weights[0].get("yes")
    return primary, bucket


def main():
    questions = load_batches()

    # id 校验
    ids = [q.get("id") for q in questions]
    if len(ids) != len(set(ids)):
        dup = [x for x in set(ids) if ids.count(x) > 1]
        error(f"id 重复: {dup}")
    for i, q in enumerate(questions):
        expect = f"Q{i + 1:05d}"
        if q.get("id") != expect:
            error(f"id 顺序/格式错误: 期望 {expect}, 实际 {q.get('id')!r}")

    # content 唯一性
    contents = [q.get("content") for q in questions]
    if len(contents) != len(set(contents)):
        dup_c = [c for c in set(contents) if contents.count(c) > 1]
        error(f"content 重复 ({len(dup_c)}): {dup_c[:5]}")

    # 逐题校验
    buckets = {d: {b: 0 for b in WEIGHT_BUCKETS} for d in DIMENSIONS}
    for q in questions:
        res = validate_question(q)
        if res:
            primary, bucket = res
            if bucket in buckets.get(primary, {}):
                buckets[primary][bucket] += 1
            else:
                error(f"{q.get('id')}: 主维度/桶不合法 {primary}/{bucket}")

    # 汇总统计
    print("=" * 60)
    print("每个 (维度, 主权重桶) 的题数:")
    print("=" * 60)
    header = "维度".ljust(18) + "".join(str(b).rjust(6) for b in WEIGHT_BUCKETS) + "   合计"
    print(header)
    total_per_dim = {}
    for dim in sorted(DIMENSIONS):
        row = dim.ljust(18)
        subtotal = 0
        for b in WEIGHT_BUCKETS:
            v = buckets[dim][b]
            subtotal += v
            mark = " " if v == EXPECTED_PER_BUCKET else "!"
            row += f"{v:>5}{mark}"
        total_per_dim[dim] = subtotal
        row += f"   {subtotal}"
        print(row)
    print("-" * 60)

    grand_total = sum(total_per_dim.values())
    print(f"总题数: {grand_total} (期望 {EXPECTED_TOTAL})")
    print()

    # 断言各维度桶数 = 4，各维度总数 = 40
    for dim in DIMENSIONS:
        for b in WEIGHT_BUCKETS:
            if buckets[dim][b] != EXPECTED_PER_BUCKET:
                error(f"{dim} 权重桶 {b}: 期望 {EXPECTED_PER_BUCKET} 题, 实际 {buckets[dim][b]} 题")
        if total_per_dim[dim] != EXPECTED_PER_DIM:
            error(f"{dim}: 期望 {EXPECTED_PER_DIM} 题, 实际 {total_per_dim[dim]} 题")

    if grand_total != EXPECTED_TOTAL:
        error(f"总题数 {grand_total} != {EXPECTED_TOTAL}")

    # 输出结果
    if errors:
        print(f"校验失败，共 {len(errors)} 个问题:")
        for e in errors:
            print("  -", e)
        sys.exit(1)

    # 写入正式题库（去掉内部 _batch 字段）
    output = []
    for q in questions:
        qq = {k: v for k, v in q.items() if k != "_batch"}
        output.append(qq)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"✓ 全部校验通过！已生成 {OUTPUT_PATH}（{len(output)} 题）")


if __name__ == "__main__":
    main()
