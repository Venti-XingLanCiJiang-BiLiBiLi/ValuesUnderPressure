# -*- coding: utf-8 -*-
"""合并并校验题库分桶文件，生成 question-bank/questions.json 与索引。

用法:
    python build_questions.py

目录结构（每桶 4 题，experimental 例外）:
    question-bank/
    ├── questions/
    │   ├── self_protection/   SP_Bnk-5.json ... SP_Bnk5.json     # 每桶 4 题
    │   ├── freedom/           FD_Bnk-5_1.json ... FD_Bnk5_2.json  # 8 题拆 2 桶(各 4 题)
    │   ├── ...
    │   ├── must/              Must_Bnk01.json ... Must_Bnk10.json # 每桶 4 题
    │   └── experimental/      Exp_Bnk01.json                      # 20 题不分桶
    ├── questions.json         # 合并后的正式题库（后端唯一数据源, 500 题）
    ├── questions.index.json   # 结构记录：各组题数/桶数/每桶数量/文件位置
    └── build_questions.py     # 本脚本

校验项 (对应 docs/DataValidation.md):
  - 总题数 / 每维度题数
  - 每个 (维度, 主权重桶) 的题数 (目标: 10 桶 x 4 题 = 40/维度, freedom=80)
  - 每桶文件题数 (常规 4 题/桶, experimental 例外)
  - id 唯一且连续 (Q00001..Q00500)
  - type 必须为 YN
  - category / difficulty 取值合法 (含 must / experimental)
  - 权重范围 -5..5, yes/no 不同时为 0, 同题同维度不重复
  - dimension 必须在合法维度集合内
  - content 非空且无重复
  - must 分类: 40 题, 10 桶各 4 题
  - experimental 分类: 20 题, 不分桶
"""

import json
import os
import re
import sys
from datetime import datetime, timezone

# 脚本位于 question-bank/ 根目录下
ROOT = os.path.dirname(os.path.abspath(__file__))
QUESTIONS_DIR = os.path.join(ROOT, "questions")
OUTPUT_PATH = os.path.join(ROOT, "questions.json")
INDEX_PATH = os.path.join(ROOT, "questions.index.json")
DIMENSIONS_FILE = os.path.join(ROOT, "dimensions.json")

errors = []


def error(msg):
    errors.append(msg)


def load_dimensions_meta():
    """从 dimensions.json 读取维度元数据（英文 ID → 中文元数据 + abbr）。

    作为本版本题库的单一数据源：维度集合 DIMENSIONS、文件名缩写 ABBR 均由它派生。
    返回 {dim: meta}；文件缺失/非法时记录错误并返回 {}。
    """
    if not os.path.isfile(DIMENSIONS_FILE):
        error(f"缺少维度元数据文件: {DIMENSIONS_FILE}")
        return {}
    with open(DIMENSIONS_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)
    if not isinstance(raw, dict) or not raw:
        error(f"dimensions.json 顶层应为非空对象: {DIMENSIONS_FILE}")
        return {}
    for dim, meta in raw.items():
        if not isinstance(meta, dict):
            error(f"维度 {dim} 的元数据应为对象")
            continue
        for key in ("abbr", "name", "description", "direction", "high", "low"):
            if key not in meta:
                error(f"维度 {dim} 缺少字段: {key}")
        direction = meta.get("direction")
        if not (isinstance(direction, list) and len(direction) == 2):
            error(f"维度 {dim} 的 direction 应为长度为 2 的数组")
    return raw


DIMENSIONS_META = load_dimensions_meta()
DIMENSIONS = set(DIMENSIONS_META.keys())
# 分桶目录按主维度组织，目录名 = 维度名；must / experimental 为特殊目录
DIMENSION_DIRS = sorted(DIMENSIONS)
SPECIAL_DIRS = ["must", "experimental"]

CATEGORIES = {
    "personal_boundary", "privacy", "freedom", "safety", "wealth",
    "morality", "social", "future", "risk", "control",
    "must", "experimental",
}
DIFFICULTIES = {"easy", "medium", "hard"}
WEIGHT_BUCKETS = [-5, -4, -3, -2, -1, 1, 2, 3, 4, 5]
EXPECTED_TOTAL = 500
# 各维度期望题数；freedom 维度题池翻倍为 80（每权重桶 8 题，拆 2 个桶文件）
EXPECTED_PER_DIM = {dim: 40 for dim in DIMENSIONS}
EXPECTED_PER_DIM["freedom"] = 80
# 各维度每个主权重桶的期望题数
EXPECTED_PER_BUCKET = {dim: {b: 4 for b in WEIGHT_BUCKETS} for dim in DIMENSIONS}
EXPECTED_PER_BUCKET["freedom"] = {b: 8 for b in WEIGHT_BUCKETS}

# 每桶文件题数上限（experimental 例外：不分桶）
BUCKET_FILE_SIZE = 4

# must 分类（必答）：40 题, 10 桶各 4 题（对应 selection.py 的 MUST_BUCKET_SIZE=4）
MUST_TOTAL = 40
MUST_BUCKET_SIZE = 4
# experimental 分类（实验性）：20 题, 不分桶
EXP_TOTAL = 20

# 维度目录 -> 文件名前缀（由 dimensions.json 的 abbr 字段派生）
ABBR = {d: meta["abbr"] for d, meta in DIMENSIONS_META.items()}

# 桶文件名模式：
#   常规维度: {ABBR}_Bnk-5.json / {ABBR}_Bnk5.json
#   freedom : {ABBR}_Bnk-5_1.json（8 题拆 2 桶时带 _part 后缀）
#   must    : Must_Bnk01.json
#   exp     : Exp_Bnk01.json
BUCKET_FILE_RE = re.compile(r"^(?P<prefix>[A-Za-z]+)_Bnk(?P<bucket>-?\d+)(?:_(?P<part>\d+))?\.json$")


def _bucket_files(group_dir: str):
    """返回该目录下排序后的桶文件名列表。"""
    path = os.path.join(QUESTIONS_DIR, group_dir)
    if not os.path.isdir(path):
        error(f"缺少分桶目录: {group_dir}")
        return []
    names = [n for n in os.listdir(path) if n.endswith(".json")]
    return sorted(names)


def load_buckets():
    """读取所有桶文件，返回 (group_dir, fname, bucket_key, questions) 列表。"""
    loaded = []
    for group_dir in DIMENSION_DIRS + SPECIAL_DIRS:
        for fname in _bucket_files(group_dir):
            fpath = os.path.join(QUESTIONS_DIR, group_dir, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                error(f"{group_dir}/{fname}: 顶层不是数组")
                continue
            # 校验文件命名是否符合约定
            m = BUCKET_FILE_RE.match(fname)
            if not m:
                error(f"{group_dir}/{fname}: 桶文件名不符合约定 {BUCKET_FILE_RE.pattern}")
            bucket_key = m.group("bucket") if m else fname
            loaded.append((group_dir, fname, bucket_key, data))
    return loaded


def validate_question(q, where):
    """单题校验，返回主维度与主权重桶；非法时返回 (None, None)。"""
    qid = q.get("id", "<no-id>")
    where = f"{where} / {qid}"

    content = q.get("content", "")
    if not isinstance(content, str) or not content.strip():
        error(f"{where}: content 为空")

    if q.get("type") != "YN":
        error(f"{where}: type 必须为 YN, 实际为 {q.get('type')!r}")

    if q.get("category") not in CATEGORIES:
        error(f"{where}: category 非法 -> {q.get('category')!r}")

    if q.get("difficulty") not in DIFFICULTIES:
        error(f"{where}: difficulty 非法 -> {q.get('difficulty')!r}")

    tags = q.get("tags", [])
    if not isinstance(tags, list) or not tags:
        error(f"{where}: tags 为空")

    weights = q.get("weights", [])
    if not isinstance(weights, list) or not weights:
        error(f"{where}: weights 为空")
        return None, None
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

    primary = weights[0].get("dimension")
    bucket = weights[0].get("yes")
    return primary, bucket


def _dump_json(obj):
    """生成与既有 questions.json 一致的格式化：缩进 2 空格，
    但对象内名为 `tags` 的数组保持紧凑单行（其余数组/对象展开）。"""
    def _fmt(v, level, compact=False):
        pad = "  " * level
        if isinstance(v, dict):
            if not v:
                return "{}"
            items = []
            for k, val in v.items():
                key = json.dumps(k, ensure_ascii=False)
                if k == "tags" and isinstance(val, list):
                    items.append(f"{pad}  {key}: {json.dumps(val, ensure_ascii=False)}")
                elif isinstance(val, (dict, list)):
                    items.append(f"{pad}  {key}: {_fmt(val, level + 1)}")
                else:
                    items.append(f"{pad}  {key}: {json.dumps(val, ensure_ascii=False)}")
            return "{\n" + ",\n".join(items) + f"\n{pad}}}"
        if isinstance(v, list):
            if not v:
                return "[]"
            if compact:
                return "[" + ", ".join(json.dumps(x, ensure_ascii=False) for x in v) + "]"
            items = [_fmt(x, level + 1) for x in v]
            return "[\n" + ",\n".join(f"{pad}  {x}" for x in items) + f"\n{pad}]"
        return json.dumps(v, ensure_ascii=False)

    return _fmt(obj, 0)


def main():
    buckets = load_buckets()
    if not buckets:
        error("未读取到任何桶文件，请检查 questions/ 目录")
        sys.exit(1)

    questions = []
    index_groups = []
    for group_dir, fname, bucket_key, qs in buckets:
        # 校验每桶文件题数（experimental 例外）
        if group_dir != "experimental" and len(qs) > BUCKET_FILE_SIZE:
            error(f"{group_dir}/{fname}: 每桶应不超过 {BUCKET_FILE_SIZE} 题, 实际 {len(qs)}")
        for q in qs:
            q["_where"] = f"{group_dir}/{fname}"
        questions.extend(qs)

        # 累积索引信息
        index_groups.append({
            "group": group_dir,
            "file": f"{group_dir}/{fname}",
            "bucket": bucket_key,
            "count": len(qs),
        })

    # id 校验：唯一且连续（Q00001..Q00500），与桶文件读取顺序无关
    ids = [q.get("id") for q in questions]
    if len(ids) != len(set(ids)):
        dup = [x for x in set(ids) if ids.count(x) > 1]
        error(f"id 重复: {dup}")
    for i, qid in enumerate(sorted(ids, key=lambda s: int(s[1:]))):
        expect = f"Q{i + 1:05d}"
        if qid != expect:
            error(f"id 连续/格式错误: 第 {i + 1} 个应为 {expect}, 实际 {qid!r}")
            break

    # content 唯一性
    contents = [q.get("content") for q in questions]
    if len(contents) != len(set(contents)):
        dup_c = [c for c in set(contents) if contents.count(c) > 1]
        error(f"content 重复 ({len(dup_c)}): {dup_c[:5]}")

    # 逐题校验
    for q in questions:
        validate_question(q, q.pop("_where", "?"))

    # 按 (维度, 主权重桶) 统计
    buckets_stat = {d: {b: 0 for b in WEIGHT_BUCKETS} for d in DIMENSIONS}
    for q in questions:
        if q.get("category") in ("must", "experimental"):
            continue
        primary = q["weights"][0]["dimension"]
        bucket = q["weights"][0]["yes"]
        if bucket in buckets_stat.get(primary, {}):
            buckets_stat[primary][bucket] += 1
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
            v = buckets_stat[dim][b]
            subtotal += v
            mark = " " if v == EXPECTED_PER_BUCKET[dim][b] else "!"
            row += f"{v:>5}{mark}"
        total_per_dim[dim] = subtotal
        row += f"   {subtotal}"
        print(row)
    print("-" * 60)
    core_total = sum(total_per_dim.values())
    print(f"常规分类总题数: {core_total}")
    print()

    for dim in DIMENSIONS:
        for b in WEIGHT_BUCKETS:
            exp = EXPECTED_PER_BUCKET[dim][b]
            if buckets_stat[dim][b] != exp:
                error(f"{dim} 权重桶 {b}: 期望 {exp} 题, 实际 {buckets_stat[dim][b]} 题")
        exp_total = EXPECTED_PER_DIM[dim]
        if total_per_dim[dim] != exp_total:
            error(f"{dim}: 期望 {exp_total} 题, 实际 {total_per_dim[dim]} 题")

    # must
    must_qs = [q for q in questions if q.get("category") == "must"]
    if len(must_qs) != MUST_TOTAL:
        error(f"must 分类: 期望 {MUST_TOTAL} 题, 实际 {len(must_qs)}")
    # must 桶文件数（每桶 MUST_BUCKET_SIZE 题）
    must_files = [g for g in index_groups if g["group"] == "must"]
    if must_files and any(g["count"] != MUST_BUCKET_SIZE for g in must_files):
        bad = [g["file"] for g in must_files if g["count"] != MUST_BUCKET_SIZE]
        error(f"must 桶文件题数异常: {bad} (应每桶 {MUST_BUCKET_SIZE} 题)")
    for q in must_qs:
        if q.get("category") != "must":
            error(f"{q.get('id')}: must 分类应为 'must'")
    print(f"must 分类: {len(must_qs)} 题, {len(must_files)} 桶 x {MUST_BUCKET_SIZE} 题")

    # experimental
    exp_qs = [q for q in questions if q.get("category") == "experimental"]
    if len(exp_qs) != EXP_TOTAL:
        error(f"experimental 分类: 期望 {EXP_TOTAL} 题, 实际 {len(exp_qs)}")
    for q in exp_qs:
        if q.get("category") != "experimental":
            error(f"{q.get('id')}: experimental 分类应为 'experimental'")
    print(f"experimental 分类: {len(exp_qs)} 题（不分桶）")

    grand_total = len(questions)
    print(f"总题数: {grand_total} (期望 {EXPECTED_TOTAL})")
    print()
    if grand_total != EXPECTED_TOTAL:
        error(f"总题数 {grand_total} != {EXPECTED_TOTAL}")

    if errors:
        print(f"校验失败，共 {len(errors)} 个问题:")
        for e in errors:
            print("  -", e)
        sys.exit(1)

    # 按 id 排序输出（保证 Q00001..Q00500 顺序稳定）
    questions.sort(key=lambda q: q["id"])
    output = []
    for q in questions:
        output.append({k: v for k, v in q.items() if not k.startswith("_")})

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(_dump_json(output))
        f.write("\n")
    print(f"✓ 全部校验通过！已生成 {OUTPUT_PATH}（{len(output)} 题）")

    # 生成索引（结构记录）：各组题数、桶数、每桶数量、文件位置
    _write_index(index_groups, grand_total)
    print(f"✓ 已生成 {INDEX_PATH}")


def _write_index(index_groups, total):
    """把桶文件清单整理成按组(group)聚合的结构记录。"""
    from collections import OrderedDict

    groups = OrderedDict()
    for g in index_groups:
        groups.setdefault(g["group"], []).append(g)

    group_list = []
    for name in DIMENSION_DIRS + SPECIAL_DIRS:
        files = groups.get(name, [])
        if not files:
            continue
        kind = "dimension" if name in DIMENSIONS else name
        sizes = {f["count"] for f in files}
        bucket_size = sizes.pop() if len(sizes) == 1 else sorted(sizes)
        entry = {
            "name": name,
            "type": kind,
            "bucket_size": bucket_size,
            "bucket_count": len(files),
            "question_count": sum(f["count"] for f in files),
            "files": [
                {
                    "path": f"questions/{f['file']}",
                    "bucket": f["bucket"],
                    "questions": f["count"],
                }
                for f in files
            ],
        }
        group_list.append(entry)

    index = {
        "version": 1,
        "description": "题库分桶索引：记录各组题数、桶（bank）数与每桶数量、文件位置。"
                       "后端仍以 questions.json（合并产物）为唯一数据源。",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_questions": total,
        "groups": group_list,
    }
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
