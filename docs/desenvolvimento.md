# Desenvolvimento local

## Pré-requisitos

- Docker Engine com Compose v2.
- Portas 3000, 3001, 8000, 5433, 9000 e 9001 livres.

## Configuração

Copie o exemplo versionado:

```bash
cp .env.example .env
```

O Compose cria o banco PostgreSQL, executa a migration Alembic e aplica seed fictício na primeira subida.

## Comandos

```bash
docker compose up --build -d
docker compose ps
docker compose logs -f postgres minio api web admin
docker compose down
```

## Qualidade

```bash
docker compose exec -T -e RUFF_CACHE_DIR=/tmp/ruff api ruff check app tests
docker compose exec -T -e MYPY_CACHE_DIR=/tmp/mypy api mypy app
docker compose exec -T api pytest -q -p no:cacheprovider
docker compose exec -T web npm run typecheck
docker compose exec -T web npm run build
docker compose exec -T admin npm run typecheck
docker compose exec -T admin npm run build
```

Para recriar somente os dados fictícios, derrube o ambiente removendo o volume do PostgreSQL e suba novamente. Nunca usar contra um ambiente com dados úteis.

## Importação do dump V1

Para importar dados do Laravel V1, use o MySQL temporário via profile:

```bash
docker compose --profile mysql-import up -d mysql
# Seguir procedimento em docs/migracao-postgresql.md
docker compose --profile mysql-import stop mysql
```

## Dados fictícios do sistema de ponto

Para popular o tenant `empresa-demo` com um cenário completo do módulo de ponto (locais com
geofencing, setores, 10 funcionários com PIN, escala dos últimos 28 dias, batidas com atraso/falta/
esquecimento propositais, banco de horas calculado + saldo inicial, ajustes de ponto nos três
status e contracheques), use `api/scripts/seed_timeclock_demo.py`. Reaproveita o `service.py` real
do domínio `timeclock` (mesma auditoria e regras de negócio da aplicação), não é INSERT direto.

`scripts/` não é montado como volume no container (só `app/`, `tests/` e `alembic/` são), então
precisa copiar antes de rodar:

```bash
docker cp api/scripts/seed_timeclock_demo.py registro-api-1:/tmp/seed_timeclock_demo.py
docker exec -e PYTHONPATH=/app -w /app registro-api-1 python /tmp/seed_timeclock_demo.py
```

Login de teste depois do seed: matrícula `DEMO-001` a `DEMO-010`, PIN `123456`, no `colaborador/`.
Recusa rodar com `ENVIRONMENT=production` e é idempotente (aborta cedo se `DEMO-001` já existir) —
seguro rodar mais de uma vez.

## Verificação end-to-end no navegador (`web/`)

Para validar visualmente uma tela do `web/` (login, preencher formulário, subir
arquivo, conferir screenshot) sem `chromium-cli` instalado no ambiente, use o
skill `web/.claude/skills/run-web/` — driver Playwright em `driver.mjs` que lê
comandos (`nav`, `fill`, `click`, `screenshot`, `console-errors`, etc.) de
stdin, no mesmo espírito do `chromium-cli`. Instruções completas, incluindo o
contorno necessário para rodar o Chromium do Playwright sem acesso root
(extração local do `.deb` de `libasound2t64`), estão em
`web/.claude/skills/run-web/SKILL.md`.

## Regras

- Nunca copiar `.env` da V1 para o repositório.
- Não editar `docs/v1/`; ela é referência local.
- Toda feature inclui testes proporcionais, documentação e validação Docker.
