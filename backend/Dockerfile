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

# migrations — prestart runs `alembic upgrade head`, which needs both the config
# and the version scripts present in the image
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic

RUN mkdir -p /data/uploads

EXPOSE 8000

# wait for the DB, migrate, seed the admin, then serve
CMD ["sh", "-c", "python -m app.prestart && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
