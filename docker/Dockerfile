FROM python:3.12-slim

# 系统依赖（curl 健康检查 / ffmpeg 视频合成 / 中文字体渲染）
RUN sed -i 's|deb.debian.org|mirrors.cloud.tencent.com|g' /etc/apt/sources.list.d/debian.sources \
    && apt-get -o Acquire::Retries=3 update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 利用 docker layer cache：requirements 单独 COPY 先 install
COPY requirements.txt .
RUN pip install --no-cache-dir --retries 5 --timeout 120 \
    -i https://mirrors.cloud.tencent.com/pypi/simple \
    -r requirements.txt

# 业务代码
COPY backend/ ./backend/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY configs/ ./configs/
COPY knowledge_base/ ./knowledge_base/
COPY scripts/ ./scripts/
COPY data/seed.json data/seed_extended.json data/question_bank.json data/cov_demo_cases.json data/variant_demo_samples.json ./data/

# 演示资产 + 数据目录
RUN mkdir -p /app/data/artifacts /app/data/cache /app/logs

# 离线演示模式默认开启（无 LLM API Key 也能跑）
ENV A3_OFFLINE_DEMO=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -fsS http://localhost:8000/api/v1/system/status || exit 1

CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
