FROM python:3.12.10-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN groupadd --system otsoc && useradd --system --gid otsoc --home-dir /app otsoc

WORKDIR /app

COPY backend/requirements.lock ./requirements.lock
RUN python -m pip install --no-cache-dir --requirement requirements.lock

FROM base AS test

ENV OTSOC_REPOSITORY_ROOT=/workspace \
    RUFF_CACHE_DIR=/tmp/ruff-cache \
    MYPY_CACHE_DIR=/tmp/mypy-cache

COPY backend/requirements-dev.lock ./requirements-dev.lock
RUN python -m pip install --no-cache-dir --requirement requirements-dev.lock

COPY --chown=otsoc:otsoc backend/app ./app
COPY --chown=otsoc:otsoc backend/tests ./tests
COPY --chown=otsoc:otsoc backend/alembic ./alembic
COPY --chown=otsoc:otsoc backend/alembic.ini ./alembic.ini
COPY --chown=otsoc:otsoc backend/pyproject.toml ./pyproject.toml
COPY --chown=otsoc:otsoc fixtures /fixtures
COPY --chown=otsoc:otsoc .dockerignore docker-compose.yml /workspace/
COPY --chown=otsoc:otsoc backend/Dockerfile /workspace/backend/Dockerfile
COPY --chown=otsoc:otsoc frontend/Dockerfile /workspace/frontend/Dockerfile
COPY --chown=otsoc:otsoc contracts/openapi.json /contracts/openapi.json
COPY --chown=otsoc:otsoc backend/app /workspace/backend/app
COPY --chown=otsoc:otsoc backend/alembic /workspace/backend/alembic
COPY --chown=otsoc:otsoc fixtures /workspace/fixtures
COPY --chown=otsoc:otsoc scenarios /workspace/scenarios

USER otsoc

FROM base AS runtime

COPY --chown=otsoc:otsoc backend/app ./app
COPY --chown=otsoc:otsoc backend/alembic ./alembic
COPY --chown=otsoc:otsoc backend/alembic.ini ./alembic.ini
COPY --chown=otsoc:otsoc fixtures /fixtures

USER otsoc

EXPOSE 8000

CMD ["sh", "-c", "python -m alembic upgrade head && exec python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"]
