# GEOP (Gestão Operacional) — Contexto para o Claude

## O que é

SaaS multitenant de gestão operacional. Atende hotelaria e outros segmentos operacionais — não é um sistema exclusivo de hotel. Substitui um sistema legado Laravel/Vue por uma stack moderna: **FastAPI + SQLAlchemy async (PostgreSQL)** no backend, **Next.js 16 (App Router, Server Actions)** no frontend.

## Stack

| Camada | Tecnologia |
|---|---|
| API | Python 3.12, FastAPI, SQLAlchemy 2 async, Alembic, PyJWT, bcrypt, slowapi |
| Web | Next.js 16, TypeScript, Tailwind CSS, App Router, Server Actions |
| Admin | Next.js (painel plataforma SaaS) |
| DB | PostgreSQL 17 (asyncpg) com RLS — MySQL disponível para import V1 |
| Infra | Docker Compose (dev), Docker Swarm (prod planejado) |

## Estrutura do repositório

```
api/           → FastAPI backend
  app/
    core/      → config, database, security, auth, audit, rate_limit, dependencies
    domain/    → domínios de negócio (auth, occurrences, fiscal_requests, users, ...)
      {domínio}/
        router.py   → endpoints HTTP (fino, só parsing e resposta)
        service.py  → lógica de negócio (queries, regras, notificações)
        schemas.py  → Pydantic models
    models/    → SQLAlchemy models (identity, operations, platform)
    integrations/ → Brevo (email), notificações
  alembic/     → migrations
  tests/       → pytest
web/           → Next.js frontend tenant
admin/         → Next.js frontend plataforma
docs/          → documentação técnica (fonte de verdade)
```

## Convenções

- **Isolamento por tenant**: toda query de negócio filtra por `company_id`. Nunca esquecer.
- **Service layer**: routers são finos — delegam para `service.py`. Services recebem session + params tipados, retornam objetos ou None. Routers mapeiam para HTTP.
- **Auditoria**: toda mutação gera `AuditEvent` via `record_event()`. Diff JSON campo a campo.
- **Soft delete**: `deleted_at` — registros apagados não aparecem em listagens.
- **Paginação**: todas as listas retornam `{items, total, page, page_size}`.
- **Auth**: JWT HS256. Access token (30min, type=access) + Refresh token (7d, type=refresh). Frontend guarda ambos em cookies httpOnly.
- **Rate limiting**: slowapi nos endpoints sensíveis (login, refresh).
- **Testes**: pytest + pytest-asyncio. Rodar com `.venv/bin/python -m pytest tests/ -v`.
- **Linter**: ruff (line-length=100). Rodar com `.venv/bin/python -m ruff check app/`.
- **Commit messages**: em português, descritivos. Co-authored-by Claude quando aplicável.
- **Documentação**: toda doc de desenvolvimento vai em `/docs`, sem exceção.

## Dev local com Docker

```bash
docker compose up -d          # sobe PostgreSQL, API, Web, Admin
docker compose build api      # rebuild após mudar pyproject.toml
docker restart geop-api-1     # restart rápido (volumes montam o código)
docker logs geop-api-1 --tail 30  # debug
```

- API: `localhost:8000` | Web: `localhost:3000` | Admin: `localhost:3001` | PostgreSQL: `localhost:5433`
- A API roda migrations e seed automaticamente no startup do container.

## Domínios implementados

auth, dashboard, occurrences, fiscal_requests, users, registries, modules, procedures, notifications, timeline, settings, platform, health
