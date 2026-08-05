"""
题库版本 manifest 校验模块。

目标：确保同一个题库版本目录内 `questions.json` 与 `dimensions.json` 永远属于
同一份题库数据，避免「题库版本和维度定义不匹配」导致测评结果错误。

目标目录结构：

    question-bank/
      v1/
        manifest.json       <- 本模块校验
        questions.json
        dimensions.json

manifest.json 内容：

    {
      "schema_version": "1",
      "bank_version": "v1",
      "questions_file": "questions.json",
      "dimensions_file": "dimensions.json",
      "questions_sha256": "...",
      "dimensions_sha256": "..."
    }

校验项（validate_manifest）：
  1. 文件存在检查（manifest.json 存在且可解析）
  2. schema_version 检查（与 SCHEMA_VERSION 一致）
  3. questions_file / dimensions_file 文件名引用检查（引用的文件必须存在）
  4. questions.json sha256 校验
  5. dimensions.json sha256 校验

设计说明：
  - 本模块只做**校验**，不改动任何题库加载路径（load_bucket_bank /
    _load_dimensions 等既有 API 行为不变），保持向后兼容；
  - manifest 的生成由 scripts/generate_manifest.py 负责；
  - 校验失败统一抛 ManifestError，message 面向运维、含可操作的修复建议。
"""

from __future__ import annotations

import hashlib
import json
import os

# manifest 文件名与当前 schema 版本（升级字段结构时递增，旧 manifest 需重新生成）。
MANIFEST_FILENAME = "manifest.json"
SCHEMA_VERSION = "1"

# manifest 中的必填顶层字段（用于缺失字段的友好报错）。
_REQUIRED_FIELDS = (
    "schema_version",
    "bank_version",
    "questions_file",
    "dimensions_file",
    "questions_sha256",
    "dimensions_sha256",
)


class ManifestError(Exception):
    """manifest 校验失败。message 面向运维，含可操作的修复建议。"""


def compute_sha256(path: str) -> str:
    """计算文件 sha256 十六进制摘要（分块读取，避免大文件占用内存）。"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_text_sha256(path: str) -> str:
    """计算文本文件（UTF-8）的 sha256，计算前先把换行规范化为 LF（CRLF -> LF）。

    题库 JSON 在 Windows（core.autocrlf=true）工作区为 CRLF，而 git 仓库与
    Linux 服务器/CI checkout 出来是 LF；若按原始字节哈希，manifest 会因换行符
    不同而跨平台不一致。规范化后无论在哪台机器生成/校验，questions.json 与
    dimensions.json 的哈希都稳定等于 git 版本，生产环境不再误报"manifest 不对应"。
    """
    with open(path, "r", encoding="utf-8") as f:
        text = f.read().replace("\r\n", "\n")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_manifest(bank_dir: str) -> dict:
    """读取题库版本目录的 manifest.json；缺失或非法时抛 ManifestError。"""
    path = os.path.join(bank_dir, MANIFEST_FILENAME)
    if not os.path.isfile(path):
        raise ManifestError(
            f"manifest 缺失: {path}\n"
            f"修复建议: 运行 python scripts/generate_manifest.py {bank_dir} 生成。"
        )
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise ManifestError(f"manifest 解析失败: {path}: {e}") from e
    if not isinstance(raw, dict):
        raise ManifestError(f"manifest 顶层应为对象: {path}")
    return raw


def build_manifest(bank_dir: str) -> dict:
    """计算题库版本目录内 questions.json / dimensions.json 的 sha256，组装 manifest。

    供 scripts/generate_manifest.py 与各版本 build_questions.py 复用（唯一实现）。
    """
    questions_path = os.path.join(bank_dir, "questions.json")
    dimensions_path = os.path.join(bank_dir, "dimensions.json")
    for label, p in (("questions.json", questions_path), ("dimensions.json", dimensions_path)):
        if not os.path.isfile(p):
            raise FileNotFoundError(f"缺少 {label}: {p}")
    bank_version = os.path.basename(os.path.abspath(bank_dir))
    return {
        "schema_version": SCHEMA_VERSION,
        "bank_version": bank_version,
        "questions_file": "questions.json",
        "dimensions_file": "dimensions.json",
        # 用换行规范化（LF）后的哈希，保证跨平台（Windows/Linux/CI）一致
        "questions_sha256": compute_text_sha256(questions_path),
        "dimensions_sha256": compute_text_sha256(dimensions_path),
    }


def validate_manifest(bank_dir: str) -> dict:
    """校验题库版本目录的 manifest，返回 manifest 内容；失败抛 ManifestError。

    校验项见模块 docstring（文件存在 / schema_version / 文件名引用 /
    questions.json hash / dimensions.json hash）。
    """
    manifest = load_manifest(bank_dir)
    bank_version = manifest.get("bank_version", "?")

    # 必填字段存在性
    missing = [k for k in _REQUIRED_FIELDS if not manifest.get(k)]
    if missing:
        raise ManifestError(
            f"[{bank_version}] manifest 缺少必填字段: {', '.join(missing)}\n"
            f"修复建议: 重新生成 manifest（scripts/generate_manifest.py）。"
        )

    # schema_version 检查
    if manifest["schema_version"] != SCHEMA_VERSION:
        raise ManifestError(
            f"[{bank_version}] manifest schema_version 不匹配: "
            f"期望 {SCHEMA_VERSION!r}，实际 {manifest['schema_version']!r}\n"
            f"修复建议: 使用当前 scripts/generate_manifest.py 重新生成 manifest。"
        )

    # 文件名引用检查 + hash 校验
    q_path = os.path.join(bank_dir, manifest["questions_file"])
    d_path = os.path.join(bank_dir, manifest["dimensions_file"])
    if not os.path.isfile(q_path):
        raise ManifestError(
            f"[{bank_version}] manifest 引用的题目文件不存在: {q_path}\n"
            f"修复建议: 检查 questions_file 引用与题库目录，重新生成 manifest。"
        )
    if not os.path.isfile(d_path):
        raise ManifestError(
            f"[{bank_version}] manifest 引用的维度文件不存在: {d_path}\n"
            f"修复建议: 检查 dimensions_file 引用与题库目录，重新生成 manifest。"
        )
    _verify_hash(
        bank_version,
        q_path,
        manifest["questions_sha256"],
        "questions.json",
    )
    _verify_hash(
        bank_version,
        d_path,
        manifest["dimensions_sha256"],
        "dimensions.json",
    )
    return manifest


def _verify_hash(bank_version: str, path: str, expected: str, label: str) -> None:
    """校验单文件 sha256（与生成端一致，按 LF 规范化换行计算）。

    不一致时抛 ManifestError（含实际/期望哈希与修复建议）。
    """
    actual = compute_text_sha256(path)
    if actual.lower() != expected.lower():
        raise ManifestError(
            f"[{bank_version}] {label} 与 manifest 不一致（题库数据已变更）:\n"
            f"  文件: {path}\n"
            f"  期望 sha256: {expected}\n"
            f"  实际 sha256: {actual}\n"
            f"修复建议: 确认 questions.json 与 dimensions.json 属于同一题库版本后，"
            f"重新生成 manifest（scripts/generate_manifest.py）。"
        )
