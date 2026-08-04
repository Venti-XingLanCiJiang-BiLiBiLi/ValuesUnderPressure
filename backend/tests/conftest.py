"""pytest 共享配置。

在导入 app.db / app.main 之前先设置环境变量：
  - APERSONALITYTEST_DB_PATH -> 临时 SQLite 文件（避免污染真实数据库）
  - QUESTION_BANK_PATH       -> 测试专用题库 fixture
"""
import os
import sys
import tempfile

BACKEND_DIR = os.path.join(os.path.dirname(__file__), "..")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

_tmp = tempfile.mkdtemp(prefix="vup_tests_")
os.environ["APERSONALITYTEST_DB_PATH"] = os.path.join(_tmp, "test.db")
os.environ["QUESTION_BANK_PATH"] = os.path.join(
    os.path.dirname(__file__), "fixtures", "questions.json"
)

import pytest

from app import db


@pytest.fixture(scope="session", autouse=True)
async def _init_test_db():
    await db.init_db()
    yield
