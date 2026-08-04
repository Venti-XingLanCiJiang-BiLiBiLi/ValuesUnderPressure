# ============================================================================
# VUP 后端镜像 (FastAPI + SQLite)
# ----------------------------------------------------------------------------
# 构建上下文必须是【仓库根目录】（后端需要 question-bank/v1 题库）：
#   docker build -f backend/Dockerfile .
#   docker compose build backend
#
# 题库路径约定：backend/app/question_bank.py 中
#   版本目录 = question-bank/<QUESTION_BANK_VERSION>/（默认 v1）
#   - 抽题主数据源：questions.index.json（分桶索引，懒加载桶文件）
#   - 合并题库：questions.json（统计/回退）
# 镜像内路径 /question-bank/v1 与代码逻辑一致（版本由 QUESTION_BANK_VERSION 控制）。
# 注意：Dockerfile 的 COPY 源路径不支持 ARG 动态插值，故构建时固定 COPY v1；
#       若要发布其它题库版本，需把 COPY 路径改为对应的版本目录。
# ============================================================================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# 1) 依赖清单先行，利用 Docker 层缓存
#    PIP_INDEX_URL：pip 镜像源，构建时可覆盖（默认官方源）。
#    国内云服务器直连 pypi.org 下载 pydantic_core 等 wheel 极易超时，
#    建议改为阿里云/清华源：
#      docker compose build --build-arg PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/
#    或直接修改 docker-compose.yml 中该 ARG 的默认值。
ARG PIP_INDEX_URL=https://pypi.org/simple
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -i "$PIP_INDEX_URL" -r requirements.txt

# 2) 后端代码
COPY backend/app /app/app

# 3) 正式题库（按版本目录，与代码分离；默认 v1）
COPY question-bank/v1 /question-bank/v1

# 4) 生产运行环境
ENV APP_ENV=production \
    APERSONALITYTEST_DB_PATH=/data/app.db \
    QUESTION_BANK_VERSION=v1

# SQLite 数据卷挂载点（docker-compose 中挂载命名卷 vup-data:/data）
VOLUME /data

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3); sys.exit(0)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
