FROM python:3.12.11-slim-bookworm AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    MYPY_CACHE_DIR=/tmp/.mypy_cache \
    RUFF_CACHE_DIR=/tmp/.ruff_cache

WORKDIR /app

RUN addgroup --system registro \
    && adduser --system --ingroup registro registro

COPY pyproject.toml ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic
RUN pip install .

FROM base AS development

RUN pip install '.[dev]'
COPY tests ./tests
USER registro
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

FROM base AS production

USER registro
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health', timeout=3)"]
# `alembic upgrade head` roda antes do uvicorn subir — o publish.yml só troca a imagem
# do serviço, nunca aplica migration sozinho, e isso já causou 3 incidentes de 500 em
# produção (o mais recente derrubando /integrations/erpsolid, ver
# docs/registro-trabalho.md#2026-08-18). É idempotente (no-op se já está no head), então
# é seguro repetir em cada réplica/restart; com `update_config.parallelism: 1` no Swarm
# não há duas réplicas novas migrando ao mesmo tempo.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2 --access-log"]
