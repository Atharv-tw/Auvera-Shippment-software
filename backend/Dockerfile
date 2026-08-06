# FastAPI backend — production image
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    UPLOAD_DIR=/data/uploads \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# install dependencies first (cached until the lockfile changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# app source
COPY app ./app

RUN mkdir -p /data/uploads

EXPOSE 8000

# wait for the DB + seed the admin, then serve
CMD ["sh", "-c", "python -m app.prestart && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
