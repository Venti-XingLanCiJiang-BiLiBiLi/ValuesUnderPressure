# -*- coding: utf-8 -*-
"""模板题库构建脚本：从 templates/questions/ 分桶合并生成 questions.json 与索引。

用法:
    python build_questions.py

本模板演示题库分文件管理框架（与 question-bank/v1/ 同构）：
  - 仅 2 个维度（self_protection / altruism）
  - 每维度 2 个桶（主权重 -5 / 5）
  - 每桶 2 题（全为占位数据，无真实题目）
  - 生成合并产物 questions.json 与分桶索引 questions.index.json

按需扩展：
  - 维度集合 DIMENSIONS 与文件名缩写 ABBR
  - 每维度桶数与每桶题数 EXPECTED_PER_BUCKET
  - id 前缀 ID_PREFIX（模板占位用 T，正式题库用 Q，见 v1/build_questions.py）
"""

import json
import os
import re
import sys
from datetime import datetime, timezone

# 脚本位于 templates/ 目录下
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
# 分桶目录按主维度组织，目录名 = 维度名（模板不含 must / experimental）
DIMENSION_DIRS = sorted(DIMENSIONS)
SPECIAL_DIRS = []  # 模板不含 must / experimental（演示常规维度即可）

CATEGORIES = {
    "personal_boundary", "privacy", "freedom", "safety", "wealth",
    "morality", "social", "future", "risk", "control",
    "must", "experimental",
}
DIFFICULTIES = {"easy", "medium", "hard"}
EXPECTED_TOTAL = 8
# 每维度期望题数（2 桶 x 2 题 = 4）
EXPECTED_PER_DIM = {dim: 4 for dim in DIMENSIONS}
# 每维度每个主权重桶的期望题数（每桶 2 题）
EXPECTED_PER_BUCKET = {dim: {-5: 2, 5: 2} for dim in DIMENSIONS}

# 每桶文件题数上限
BUCKET_FILE_SIZE = 2
# 占位 id 前缀（正式题库用 Q）
ID_PREFIX = "T"

# 维度目录 -> 文件名前缀（由 dimensions.json 的 abbr 字段派生）
ABBR = {d: meta["abbr"] for d, meta in DIMENSIONS_META.items()}

BUCKET_FILE_RE = re.compile(r"^(?P<prefix>[A-Za-z]+)_Bnk(?P<bucket>-?\d+)\.json$")


def _bucket_files(group_dir):
    path = os.path.join(QUESTIONS_DIR, group_dir)
    if not os.path.isdir(path):
        error(f"缺少分桶目录: {group_dir}")
        return []
    return sorted(n for n in os.listdir(path) if n.endswith(".json"))


def load_buckets():
    loaded = []
    for group_dir in DIMENSION_DIRS + SPECIAL_DIRS:
        for fname in _bucket_files(group_dir):
            fpath = os.path.join(QUESTIONS_DIR, group_dir, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                error(f"{group_dir}/{fname}: 顶层不是数组")
                continue
            m = BUCKET_FILE_RE.match(fname)
            if not m:
                error(f"{group_dir}/{fname}: 桶文件名不符合约定 {BUCKET_FILE_RE.pattern}")
            bucket_key = m.group("bucket") if m else fname
            loaded.append((group_dir, fname, bucket_key, data))
    return loaded


def validate_question(q, where):
    qid = q.get("id", "<no-id>")
    where = f"{where} / {qid}"
    if not isinstance(q.get("content", ""), str) or not q.get("content", "").strip():
        error(f"{where}: content 为空")
    if q.get("type") != "YN":
        error(f"{where}: type 必须为 YN, 实际为 {q.get('type')!r}")
    if q.get("category") not in CATEGORIES:
        error(f"{where}: category 非法 -> {q.get('category')!r}")
    if q.get("difficulty") not in DIFFICULTIES:
        error(f"{where}: difficulty 非法 -> {q.get('difficulty')!r}")
    weights = q.get("weights", [])
    if not isinstance(weights, list) or not weights:
        error(f"{where}: weights 为空")
        return None, None
    seen = set()
    for w in weights:
        dim = w.get("dimension")
        yes, no = w.get("yes"), w.get("no")
        if dim not in DIMENSIONS:
            error(f"{where}: dimension 非法 -> {dim!r}")
        if dim in seen:
            error(f"{where}: 同题重复维度 {dim}")
        seen.add(dim)
        if not (-5 <= yes <= 5 and isinstance(yes, int)):
            error(f"{where}: yes 超出范围 -> {yes!r}")
        if not (-5 <= no <= 5 and isinstance(no, int)):
            error(f"{where}: no 超出范围 -> {no!r}")
        if yes == 0 and no == 0:
            error(f"{where}: {dim} 的 yes/no 同时为 0")
    return weights[0].get("dimension"), weights[0].get("yes")


def main():
    buckets = load_buckets()
    if not buckets:
        error("未读取到任何桶文件，请检查 questions/ 目录")
        sys.exit(1)

    questions = []
    index_groups = []
    for group_dir, fname, bucket_key, qs in buckets:
        if len(qs) > BUCKET_FILE_SIZE:
            error(f"{group_dir}/{fname}: 每桶应不超过 {BUCKET_FILE_SIZE} 题, 实际 {len(qs)}")
        for q in qs:
            q["_where"] = f"{group_dir}/{fname}"
        questions.extend(qs)
        index_groups.append({
            "group": group_dir, "file": f"{group_dir}/{fname}",
            "bucket": bucket_key, "count": len(qs),
        })

    # id 校验：唯一且连续（T00001..T00008），与桶读取顺序无关
    ids = [q.get("id") for q in questions]
    if len(ids) != len(set(ids)):
        dup = [x for x in set(ids) if ids.count(x) > 1]
        error(f"id 重复: {dup}")
    for i, qid in enumerate(sorted(ids, key=lambda s: int(s[1:]))):
        expect = f"{ID_PREFIX}{i + 1:05d}"
        if qid != expect:
            error(f"id 连续/格式错误: 第 {i + 1} 个应为 {expect}, 实际 {qid!r}")
            break

    # 逐题校验
    for q in questions:
        validate_question(q, q.pop("_where", "?"))

    # 按 (维度, 主权重桶) 统计
    stat = {d: {} for d in DIMENSIONS}
    for q in questions:
        primary = q["weights"][0]["dimension"]
        bucket = q["weights"][0]["yes"]
        stat.setdefault(primary, {})[bucket] = stat[primary].get(bucket, 0) + 1

    print("=" * 50)
    print("每个 (维度, 主权重桶) 的题数:")
    print("=" * 50)
    total = 0
    for dim in DIMENSION_DIRS:
        row = [f"{dim}"]
        subtotal = 0
        for b in sorted(stat[dim], key=lambda x: (x >= 0, abs(x))):
            v = stat[dim][b]
            subtotal += v
            row.append(f"{b}: {v}")
        total += subtotal
        print("  " + "  ".join(row) + f"  (合计 {subtotal})")
    print(f"总题数: {total} (期望 {EXPECTED_TOTAL})")
    if total != EXPECTED_TOTAL:
        error(f"总题数 {total} != {EXPECTED_TOTAL}")
    for dim in DIMENSIONS:
        for b, exp in EXPECTED_PER_BUCKET[dim].items():
            if stat[dim].get(b, 0) != exp:
                error(f"{dim} 权重桶 {b}: 期望 {exp} 题, 实际 {stat[dim].get(b, 0)}")

    if errors:
        print(f"校验失败，共 {len(errors)} 个问题:")
        for e in errors:
            print("  -", e)
        sys.exit(1)

    # 按 id 排序输出
    questions.sort(key=lambda q: q["id"])
    output = []
    for q in questions:
        output.append({k: v for k, v in q.items() if not k.startswith("_")})

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(_dump_json(output))
        f.write("\n")
    print(f"✓ 全部校验通过！已生成 {OUTPUT_PATH}（{len(output)} 题）")

    _write_index(index_groups, total)
    print(f"✓ 已生成 {INDEX_PATH}")

    # 联动生成 manifest（记录 questions.json / dimensions.json 的 sha256）
    _write_manifest()


def _write_manifest():
    """生成 manifest.json：记录 questions.json 与 dimensions.json 的 sha256。

    复用后端 app.manifest.build_manifest（唯一实现），确保模板与新版本骨架的
    manifest 与 v1 使用同一套逻辑。
    """
    backend_dir = os.path.abspath(os.path.join(ROOT, "..", "..", "backend"))
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    from app.manifest import MANIFEST_FILENAME, build_manifest

    manifest = build_manifest(ROOT)
    with open(os.path.join(ROOT, MANIFEST_FILENAME), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"✓ 已生成 {os.path.join(ROOT, MANIFEST_FILENAME)}")


def _dump_json(obj):
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


def _write_index(index_groups, total):
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
        group_list.append({
            "name": name,
            "type": kind,
            "bucket_size": bucket_size,
            "bucket_count": len(files),
            "question_count": sum(f["count"] for f in files),
            "files": [
                {"path": f"questions/{f['file']}", "bucket": f["bucket"], "questions": f["count"]}
                for f in files
            ],
        })

    index = {
        "version": 1,
        "description": "模板题库分桶索引：演示版本化分桶管理框架（2 维度 x 2 桶 x 2 题，全占位数据）。",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_questions": total,
        "groups": group_list,
    }
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
