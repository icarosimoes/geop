# GEOP

Sistema de gestão operacional SaaS em modernização para FastAPI + Next.js, com isolamento multitenant desde a fundação.

O Laravel e o MySQL atuais continuam sendo a fonte de verdade durante a transição. A nova aplicação vive na raiz e a versão anterior permanece arquivada localmente em `docs/v1/`:

- `api/`: FastAPI + SQLAlchemy assíncrono;
- `web/`: produto do tenant em Next.js App Router + TypeScript;
- `admin/`: painel administrativo da plataforma em Next.js;
- `docs/v1/`: aplicação Laravel legada completa, ignorada pelo Git;
- `docs/`: arquitetura, mapa, decisões e registro de trabalho.

## Desenvolvimento da nova aplicação

```bash
cp .env.example .env
docker compose up --build -d
```

O Compose cria MySQL, executa Alembic, aplica um seed fictício e sobe web, API e admin. Nunca versione credenciais ou dumps.

Leia a [documentação do projeto](./docs/README.md) antes de alterar arquitetura, banco ou contratos do legado.

## Docker

```bash
docker compose up --build
```

Produção usa exclusivamente Docker Swarm. Consulte o [runbook de deploy](./docs/infra/deploy-swarm.md).
