# Deploy do Registro em novo domínio

Procedimento reproduzível para publicar o Registro em outro domínio ou em outro Swarm. O primeiro deploy validado ocorreu em 22/06/2026; as falhas reais encontradas estão registradas no fim deste documento.

## Parâmetros do ambiente

Defina antes de começar:

```bash
export REGISTRO_WEB_HOST=registro.exemplo.com.br
export REGISTRO_API_HOST=api.registro.exemplo.com.br
export REGISTRO_ADMIN_HOST=painel.registro.exemplo.com.br
export REGISTRO_COLABORADOR_HOST=colaborador.registro.exemplo.com.br
export REGISTRO_WEB_ORIGIN=https://${REGISTRO_WEB_HOST}
export IMAGE_TAG=sha-<commit-completo-publicado-no-ghcr>
```

O navegador acessa quatro hosts, mas web, admin e colaborador consomem a API internamente em `http://api:8000/api/v1`. Não troque `API_URL` por uma URL pública no stack.

## 1. Pré-requisitos

- nó manager do Docker Swarm acessível por SSH;
- Traefik ativo e conectado à rede overlay externa `traefik-public`;
- certificate resolver conhecido e funcional;
- quatro registros DNS apontando para a VPS;
- login do Docker na VPS com permissão `read:packages` no GHCR;
- workflow `Publish images` concluído para o SHA escolhido;
- portas 80 e 443 liberadas para o Traefik.

Valide sem alterar o cluster:

```bash
docker info --format '{{.Swarm.LocalNodeState}} {{.Swarm.ControlAvailable}}'
docker node ls
docker network inspect traefik-public >/dev/null
docker service inspect traefik_traefik --format '{{json .Spec.TaskTemplate.ContainerSpec.Args}}'
```

O stack do Registro usa o resolver `letsencrypt`. Confirme que o Traefik possui `--certificatesresolvers.letsencrypt...`; o nome precisa ser idêntico nas labels.

## 2. DNS e Cloudflare

Crie registros `A` para web, API, painel e colaborador apontando para o IP público da VPS.

Hosts como `api.registro.exemplo.com.br` e `painel.registro.exemplo.com.br` têm dois níveis abaixo da zona. O certificado Universal `*.exemplo.com.br` do Cloudflare não os cobre. Escolha uma destas opções:

1. deixar os registros como **DNS-only**, usando o certificado Let’s Encrypt do Traefik; ou
2. manter proxy Cloudflare somente com certificado edge que cubra explicitamente esses hosts.

Para o primeiro deploy, DNS-only é a opção mais simples. Valide a resolução pública:

```bash
getent ahostsv4 "$REGISTRO_WEB_HOST"
getent ahostsv4 "$REGISTRO_API_HOST"
getent ahostsv4 "$REGISTRO_ADMIN_HOST"
getent ahostsv4 "$REGISTRO_COLABORADOR_HOST"
```

## 3. Validar código e publicar imagens

Antes do push que será implantado:

```bash
cd api
uv run ruff check app tests
PYTHONPATH=. uv run pytest -q

cd ../web
npm ci
npm run build

cd ../admin
npm ci
npm run build
```

O build Next.js é obrigatório: `tsc --noEmit` não detecta todos os erros de prerenderização, como `useSearchParams` fora de `Suspense`.

Depois do push, aguarde o workflow `Publish images`. Ele publica:

```text
ghcr.io/icarosimoes/registro/api:sha-<SHA>
ghcr.io/icarosimoes/registro/web:sha-<SHA>
ghcr.io/icarosimoes/registro/admin:sha-<SHA>
```

Nunca implante `latest`. O token usado pelo workflow precisa de `packages: write`; a VPS precisa apenas de leitura.

## 4. Preparar diretório e ambiente

Na VPS:

```bash
install -d -m 700 /opt/registro
install -m 600 docker-stack.yml /opt/registro/docker-stack.yml
install -m 600 /dev/null /opt/registro/.env.prod
```

Conteúdo de `/opt/registro/.env.prod`:

```env
REGISTRO_WEB_HOST=registro.exemplo.com.br
REGISTRO_API_HOST=api.registro.exemplo.com.br
REGISTRO_ADMIN_HOST=painel.registro.exemplo.com.br
REGISTRO_COLABORADOR_HOST=colaborador.registro.exemplo.com.br
REGISTRO_WEB_ORIGIN=https://registro.exemplo.com.br
IMAGE_TAG=sha-<sha-completo>
```

Não grave PAT do GHCR nesse arquivo. Faça login por `--password-stdin` e remova o token do shell após o uso.

## 5. Criar Docker Secrets

Execute uma única vez. Se algum nome já existir, audite antes de reutilizar ou substituir.

```bash
db_password="$(openssl rand -hex 32)"
jwt_secret="$(openssl rand -hex 48)"
chess_key="$(openssl rand -hex 48)"
s3_secret="$(openssl rand -hex 32)"

printf '%s' "$db_password" | docker secret create registro_postgres_password -
printf '%s' "postgresql+asyncpg://registro:${db_password}@db:5432/registro" \
  | docker secret create registro_database_url -
printf '%s' "$jwt_secret" | docker secret create registro_jwt_secret -
printf '%s' "$chess_key" | docker secret create chess_hotel_integration_key -
printf '%s' 'registro' | docker secret create registro_s3_access_key -
printf '%s' "$s3_secret" | docker secret create registro_s3_secret_key -

unset db_password jwt_secret chess_key s3_secret
```

O mesmo `db_password` deve alimentar `registro_postgres_password` e `registro_database_url`. Nunca execute dois `openssl rand` independentes para esses valores.

## 6. Renderizar e publicar o stack

```bash
cd /opt/registro
set -a
. ./.env.prod
set +a

docker stack config -c docker-stack.yml >/dev/null
docker pull "ghcr.io/icarosimoes/registro/api:${IMAGE_TAG}"
docker pull "ghcr.io/icarosimoes/registro/web:${IMAGE_TAG}"
docker pull "ghcr.io/icarosimoes/registro/admin:${IMAGE_TAG}"
docker stack deploy -c docker-stack.yml --with-registry-auth registro
```

PostgreSQL, Redis, MinIO e backups usam volumes locais e ficam fixados no manager. API e web podem ocupar os dois nós. No primeiro start, a API pode reiniciar enquanto o banco inicializa e antes das migrations; acompanhe as tasks atuais, não apenas logs históricos:

```bash
docker stack services registro
docker service ps registro_db --no-trunc
docker service ps registro_api --no-trunc
```

## 7. Aplicar migrations uma única vez

Alembic não roda no comando de inicialização da API. Crie uma tarefa temporária no manager:

```bash
docker service create \
  --name registro-migrate \
  --restart-condition none \
  --constraint 'node.role==manager' \
  --network registro_registro-internal \
  --secret registro_database_url \
  --env DATABASE_URL_FILE=/run/secrets/registro_database_url \
  "ghcr.io/icarosimoes/registro/api:${IMAGE_TAG}" \
  alembic upgrade head

docker service ps registro-migrate --no-trunc
docker service logs registro-migrate
```

Só remova depois de confirmar estado `Complete`:

```bash
docker service rm registro-migrate
```

## 8. Seed inicial ou importação V1

Em ambiente vazio, gere senhas fortes, guarde-as em arquivo root-only e execute `python -m app.seed` como tarefa temporária. Remova o serviço após estado `Complete`.

```bash
install -m 600 /dev/null /opt/registro/initial-credentials.txt
```

O seed atual reutiliza permissões já criadas pelas migrations. Não deve haver conflito em `permissions.code`.

Se o objetivo for corte do legado, não trate o seed demonstrativo como importação. Siga [Migração PostgreSQL](../migracao-postgresql.md) e [Importação do legado](importacao-legado.md), com dump atualizado e anexos físicos inventariados.

## 9. Validação obrigatória

```bash
docker stack services registro
curl -fsS "https://${REGISTRO_API_HOST}/api/v1/health"
curl -fsS "https://${REGISTRO_API_HOST}/api/v1/health/ready"
curl -fsS -o /dev/null "https://${REGISTRO_WEB_HOST}/login"
curl -fsS -o /dev/null "https://${REGISTRO_ADMIN_HOST}/login"
curl -fsS -o /dev/null "https://${REGISTRO_COLABORADOR_HOST}/login"
```

Readiness deve informar banco e cache conectados. Valide também:

- certificado e SAN dos quatro hosts;
- login tenant e login platform sem imprimir tokens;
- criação/listagem de um registro de teste quando aplicável;
- MinIO e criação do bucket pela API;
- primeiro backup não vazio e seu SHA-256;
- ausência de secrets em logs e `docker service inspect`.

Em produção, `/docs` e o OpenAPI público ficam desativados; `404` nessas rotas é esperado.

## 10. Troca futura de domínio

Para mover uma instalação existente:

1. crie os quatro novos registros DNS;
2. ajuste `REGISTRO_WEB_HOST`, `REGISTRO_API_HOST`, `REGISTRO_ADMIN_HOST`, `REGISTRO_COLABORADOR_HOST` e `REGISTRO_WEB_ORIGIN`;
3. renderize `docker stack config`;
4. aplique `docker stack deploy` com a mesma tag imutável, se não houver mudança de código;
5. aguarde o DNS challenge e valide os certificados;
6. atualize a URL usada pelo Chess Hotel e outras integrações externas;
7. mantenha os hosts antigos apenas durante a janela de transição, se isso tiver sido planejado.

Troca de domínio não exige migration nem nova imagem, salvo quando contratos ou configurações embutidas no build mudarem.

## Falhas reais encontradas no primeiro deploy

| Sintoma | Causa | Correção permanente |
| --- | --- | --- |
| GHCR recusou push com `permission_denied` | token local sem `write:packages` | workflow `Publish images` com `GITHUB_TOKEN` e `packages: write` |
| imagem web não compilou | `useSearchParams` fora de `Suspense` em `/definir-senha` | componente envolvido por `Suspense`; build Next obrigatório antes do deploy |
| API encerrou com `No module named httpx` | `httpx` estava somente nas dependências `dev` | movido para dependências de runtime em `api/pyproject.toml` |
| seed falhou com `permissions_code_key` | migrations já haviam criado permissões | seed reutiliza permissões existentes e insere somente ausentes |
| Traefik entregou certificado autoassinado | router usava resolver inexistente `le` | labels alinhadas ao resolver real `letsencrypt` |
| handshake falhou via Cloudflare | wildcard Universal não cobre subdomínio de segundo nível | DNS-only ou certificado edge explícito para o hostname |
| API apareceu `0/2` no início | banco ainda inicializando, migrations ausentes ou imagem antiga em task histórica | aplicar migrations e conferir `docker service ps --no-trunc` com digest atual |
| logs ainda mostravam erro já corrigido | `docker service logs` agrega tasks antigas | correlacionar log com ID/digest da task atual |
| primeiro backup tinha zero bytes | serviço iniciou antes do PostgreSQL estar pronto | descartar artefato vazio e validar o primeiro dump completo com `sha256sum -c` |
| `/docs` retornou `404` | documentação OpenAPI é desativada em produção | comportamento esperado; usar health/readiness para operação |

## Critério de conclusão

Deploy só está concluído quando serviços convergiram, migrations terminaram, TLS está válido, readiness confirma banco/cache, logins funcionam e existe backup íntegro. DNS respondendo ou `health` isolado não bastam.
