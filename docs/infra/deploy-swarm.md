# Deploy Docker Swarm — GEOP

## Decisão operacional

Para primeiro deploy ou troca de domínio, siga o procedimento completo em [Deploy em novo domínio](deploy-novo-dominio.md).

- Todo ambiente sobe em containers Docker.
- Desenvolvimento local usa `docker compose`.
- Produção usa Docker Swarm; não usar `docker compose up` na VPS.
- A VPS mantém a aplicação em `/opt/registro`.
- Imagens são publicadas no GHCR com tag imutável `sha-<GITHUB_SHA completo>`.
- O workflow `Publish images` publica API, web, admin e colaborador em paralelo a cada push em `main`.
- Após publicação, o job `deploy` conecta via SSH e atualiza os serviços no Swarm automaticamente.
- Deploy usa `--with-registry-auth` e atualização gradual `start-first`.
- Nenhum segredo é versionado em `.env`, stack ou imagem.

## Desenvolvimento

O desenvolvimento usa PostgreSQL, Redis e MinIO no Compose:

```bash
docker compose up --build
```

Serviços:

- web: `http://localhost:3000`
- admin: `http://localhost:3001`
- API: `http://localhost:8000`
- OpenAPI local: `http://localhost:8000/docs`

## Preparação única do Swarm

```bash
docker network create --driver overlay --attachable traefik-public
db_password="$(openssl rand -hex 32)"
jwt_secret="$(openssl rand -hex 48)"
printf '%s' "$db_password" | docker secret create registro_postgres_password -
printf '%s' "postgresql+asyncpg://registro:${db_password}@db:5432/registro" | docker secret create registro_database_url -
printf '%s' "$jwt_secret" | docker secret create registro_jwt_secret -
unset db_password jwt_secret
mkdir -p /opt/registro
```

PostgreSQL, Redis e MinIO fazem parte da stack e mantêm volumes locais fixados no manager. Um serviço gera backups diários em formato custom do PostgreSQL, com SHA-256 e retenção de 14 dias. A URL do banco, JWT e credenciais MinIO usam secrets independentes.

## Variáveis da VPS

Arquivo local `/opt/registro/.env.prod`, nunca versionado:

```env
REGISTRO_WEB_HOST=geop.solidsd.com.br
REGISTRO_API_HOST=api.geop.solidsd.com.br
REGISTRO_ADMIN_HOST=painel.geop.solidsd.com.br
REGISTRO_COLABORADOR_HOST=colaborador.geop.solidsd.com.br
REGISTRO_WEB_ORIGIN=https://geop.solidsd.com.br
IMAGE_TAG=sha-<sha-completo>
```

A API é publicada em `api.geop.solidsd.com.br`; seus endpoints permanecem sob `/api/v1`.

> Domínio trocado de `registro.solidsd.com.br` para `geop.solidsd.com.br` em 14/08/2026 (ver seção "Troca futura de domínio" em [deploy-novo-dominio.md](deploy-novo-dominio.md)). Os 4 hosts ficam DNS-only na Cloudflare (sem proxy) — Universal SSL grátis não cobre os subdomínios de 2º nível (`api.`, `painel.`, `colaborador.`), então o Traefik precisa acesso direto para emitir/renovar o certificado Let's Encrypt.

## Deploy automático (CI/CD)

O workflow `Publish images` (`.github/workflows/publish.yml`) executa dois jobs:

1. **publish** — builda e publica as imagens no GHCR com tag `sha-<commit>`.
2. **deploy** — conecta via SSH na VPS e atualiza os 4 serviços no Swarm com `docker service update --image ... --detach`.

Secrets necessários no GitHub (já configurados):

| Secret | Valor |
|---|---|
| `VPS_SSH_KEY` | Chave privada Ed25519 para `root@VPS` |
| `VPS_HOST` | IP da VPS (`95.111.250.4`) |

O deploy roda com `--detach` para não bloquear o CI. O Swarm faz rolling update conforme a `update_config` de cada serviço no `docker-stack.yml`.

## Deploy manual

Para deploy manual ou primeira instalação:

```bash
cd /opt/registro
set -a
. ./.env.prod
set +a
docker stack config -c docker-stack.yml >/dev/null
docker stack deploy -c docker-stack.yml --with-registry-auth registro
```

Para atualizar um serviço específico:

```bash
docker service update --image ghcr.io/icarosimoes/registro/web:sha-<commit> registro_web
docker service update --image ghcr.io/icarosimoes/registro/api:sha-<commit> registro_api
```

Nunca usar apenas `latest` em produção. O CI deve publicar e o deploy deve informar a tag completa baseada no SHA.

## Validação

```bash
docker service ls
docker service ps registro_api
docker service ps registro_web
docker service ps registro_admin
docker service ps registro_colaborador
docker service logs --tail 100 registro_api
curl -fsS "https://${REGISTRO_API_HOST}/api/v1/health"
```

## Rollback

```bash
docker service rollback registro_api
docker service rollback registro_web
docker service rollback registro_admin
docker service rollback registro_colaborador
```

Antes de migrations, mudanças críticas ou reboot da VPS, gerar e validar backup. Migrations futuras devem rodar uma única vez, em tarefa controlada no manager, nunca simultaneamente em todas as réplicas.

## Migrations no Swarm

O Alembic **não roda automaticamente** nas réplicas. Para aplicar migrations:

```bash
# Descobrir imagem atual da API
API_IMAGE=$(docker service inspect registro_api --format '{{.Spec.TaskTemplate.ContainerSpec.Image}}')

# Ler senha do PG de dentro do container do DB
DB_CONTAINER=$(docker ps -q -f "name=registro_db" | head -1)
PG_PASS=$(docker exec "$DB_CONTAINER" cat /run/secrets/registro_postgres_password)
DB_URL="postgresql+asyncpg://registro:${PG_PASS}@${DB_CONTAINER}:5432/registro"

# Criar rede temporária e conectar o DB
docker network create registro-migration-temp
docker network connect registro-migration-temp "$DB_CONTAINER"

# Rodar migrations
docker run --rm \
  --network registro-migration-temp \
  -e "DATABASE_URL=$DB_URL" \
  -e "JWT_SECRET=$(openssl rand -hex 48)" \
  -e "WEB_ORIGINS=https://localhost" \
  -e "ENVIRONMENT=production" \
  -e "REDIS_URL=redis://localhost:6379/0" \
  -e "SEED_DEFAULT_PASSWORD=unused" \
  -e "PLATFORM_ADMIN_PASSWORD=unused" \
  "$API_IMAGE" alembic upgrade head

# Limpar
docker network disconnect registro-migration-temp "$DB_CONTAINER"
docker network rm registro-migration-temp
```

## Importação de dados V1 (MySQL → PostgreSQL)

Para importar dados de um tenant a partir de dump MySQL da V1:

```bash
bash scripts/import-v1-swarm.sh <caminho-do-dump.sql>
```

Detalhes em [importacao-legado.md](importacao-legado.md).
