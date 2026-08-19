# Renomear a stack de produção de `registro` para `geop`

Plano para a segunda metade da pendência aberta em 2026-08-14 (ver `memoria-projeto.md`):
o dev local já foi renomeado em 19/08/2026 (`registro-*` → `geop-*`, ver
`registro-trabalho.md`), produção continua `registro-*`. **Não executado** — este agente
não tem acesso SSH à VPS nem ao GHCR, só preparou o plano. Precisa de uma janela de
manutenção dedicada (o corte da stack tem alguns minutos de indisponibilidade) e de quem
tiver acesso à VPS/GHCR para rodar os comandos.

## O que muda e o que não muda

| Item | Renomear? | Por quê |
|---|---|---|
| Nome da stack (`docker stack deploy ... geop`) | Sim | Muda o prefixo dos serviços (`registro_api` → `geop_api`) sem tocar `docker-stack.yml` — é só o último argumento do comando de deploy. |
| Pacotes GHCR (`ghcr.io/icarosimoes/registro/*`) | Sim | `publish.yml` e `docker-stack.yml` referenciam o path da imagem. |
| Secrets do Swarm (`registro_*`) | Sim | São externos ao stack; precisam existir com o nome novo antes do deploy. |
| Volumes (`registro-postgres-data`, `-minio-data`, `-backups`, `-redis-data`) | Sim, com migração de dados | Renomear sem copiar o conteúdo cria volumes vazios — banco/anexos de produção "somem" (continuam no volume antigo, órfão). |
| Rede overlay (`registro-internal`) | Sim | Cosmético, sem dado. |
| `/opt/registro` na VPS | Sim | Diretório onde `docker-stack.yml` e `.env.prod` vivem. |
| Labels do Traefik (`registro-api`, `registro-web`, ...) | Sim | Cosmético — só o nome do router/service no Traefik, não o host. |
| Nome/usuário do banco Postgres (`registro`/`registro`) | **Não, por padrão** | Renomear DB/role exige `ALTER DATABASE`/`ALTER ROLE` ou dump-restore, risco maior sem ganho — é interno, ninguém vê. Decisão separada se algum dia quiser. |
| Bucket S3/MinIO (`registro-attachments`) | **Não, por padrão** | Renomear bucket MinIO = criar bucket novo + copiar objetos + trocar `S3_BUCKET`. Mesma lógica do banco: risco sem ganho visível. |
| `APP_NAME` (`Registro API`) | Opcional | Só aparece em logs/Sentry. Trocar para `GEOP API` é seguro e independente do resto — pode ser feito a qualquer momento, sem passo de VPS. |
| Hosts públicos (`geop.solidsd.com.br` etc.) | Já feito | Trocado em 14/08/2026, não faz parte deste plano. |

## Pré-requisitos

- Acesso SSH ao manager do Swarm (`root@95.111.250.4`, ver `runbook-producao.md`).
- Acesso de push ao GHCR (`icarosimoes`) com permissão pra criar o novo path
  `ghcr.io/icarosimoes/geop/*`.
- Backup validado e recente (`scripts/backup-restore.sh` ou o backup diário automático da
  stack) antes de começar — mudança tocando volumes de produção.
- Janela de manutenção: o corte troca a stack inteira, não é rolling update. Esperar alguns
  minutos de indisponibilidade entre parar `registro` e `geop` ficar saudável.

## 1. Publicar imagens no novo path do GHCR

`.github/workflows/publish.yml` builda e publica em `ghcr.io/icarosimoes/registro/{api,web,admin,colaborador}`. Trocar o path (variável `REPO`/matriz do workflow) pra
`ghcr.io/icarosimoes/geop/{api,web,admin,colaborador}` e mesclar em `main` — isso já
publica as imagens no path novo nos próximos pushes, sem afetar o path antigo (o pacote
`registro/*` fica órfão no GHCR, não é apagado sozinho). Confirmar que o pacote novo ficou
público/acessível com a mesma visibilidade do antigo antes de seguir.

`docker-stack.yml` (produção) e `docker-service update` do runbook usam o path antigo —
atualizar todas as referências `ghcr.io/icarosimoes/registro/` → `ghcr.io/icarosimoes/geop/`
junto com o resto deste arquivo (passo 4).

## 2. Criar os secrets novos na VPS

Não dá pra renomear um secret do Swarm — cria um novo com o mesmo valor do antigo e troca
a referência no stack. Ler o valor atual em vez de gerar um novo (senha/URL diferentes
quebram a conexão com o banco já existente):

```bash
# senha do Postgres: reaproveitar o valor atual
docker secret inspect registro_postgres_password  # confirma que existe; o *valor* não é legível via inspect
# não dá pra ler o valor de um secret já criado — se não tiver guardado em outro lugar
# (gerenciador de senhas, .env.prod original), a alternativa é: manter o mesmo valor
# rodando `ALTER USER registro WITH PASSWORD '<mesma senha atual>'` não é necessário —
# só reutilize o valor que já está em produção hoje (ex.: copiar do secret via um
# container que já tem acesso, ou do arquivo onde foi gerado originalmente).

printf '%s' "$PG_PASSWORD_ATUAL" | docker secret create geop_postgres_password -
printf '%s' "postgresql+asyncpg://registro:${PG_PASSWORD_ATUAL}@db:5432/registro" | docker secret create geop_database_url -
printf '%s' "$JWT_SECRET_ATUAL" | docker secret create geop_jwt_secret -
printf '%s' "$ERPSOLID_INTEGRATION_KEY_ATUAL" | docker secret create geop_erpsolid_integration_key -
printf '%s' "$ERPSOLID_SSO_SHARED_SECRET_ATUAL" | docker secret create geop_erpsolid_sso_shared_secret -
printf '%s' "$S3_ACCESS_KEY_ATUAL" | docker secret create geop_s3_access_key -
printf '%s' "$S3_SECRET_KEY_ATUAL" | docker secret create geop_s3_secret_key -
```

> `erpsolid_integration_key`/`erpsolid_sso_shared_secret` não seguiam o prefixo `registro_`
> antes — decidir se entram no rename (`geop_erpsolid_*`) ou ficam como estão; qualquer uma
> das duas opções funciona, só precisa bater com o `secrets:` do `docker-stack.yml` novo.

**Trocar o JWT secret invalida todas as sessões ativas** (usuários vão precisar logar de
novo) — se quiser evitar isso, reaproveite o valor atual em vez de gerar um novo.

## 3. Migrar os volumes (mesma técnica usada no dev local)

Com a stack `registro` ainda rodando (não precisa parar pra isso — os volumes locais do
Swarm ficam no manager, acessíveis por um container temporário no mesmo node):

```bash
for pair in \
  registro-postgres-data:geop-postgres-data \
  registro-minio-data:geop-minio-data \
  registro-redis-data:geop-redis-data \
  registro-backups:geop-backups
do
  old="${pair%%:*}"; new="${pair##*:}"
  docker volume create "$new"
  docker run --rm -v "$old:/from:ro" -v "$new:/to" alpine sh -c "cp -a /from/. /to/"
done
```

Pra zero perda de escrita entre a cópia e o corte, faça essa cópia **depois** de parar a
stack antiga (passo 5) e **antes** de subir a nova — aceitar alguns minutos de
indisponibilidade em troca de não perder writes que aconteçam durante a cópia.

## 4. Atualizar `docker-stack.yml` e os scripts

No repo (`docker-stack.yml`, `scripts/backup-restore.sh`, `scripts/import-v1-swarm.sh`,
`.github/workflows/publish.yml`): todas as ocorrências de `registro_*` (secrets, imagem
GHCR), `registro-internal` (rede), `registro-*-data`/`registro-backups` (volumes) e
`registro_api`/`registro_web`/`registro_admin`/`registro_colaborador`/`registro_db` (nomes
de serviço usados em `docker service update`/`docker service ps`/scripts) trocam pra
`geop_*`. Labels do Traefik (`traefik.http.routers.registro-*`) também — cosmético, mas
mantenha consistente.

Atualizar também `docs/infra/runbook-producao.md`, `docs/infra/deploy-swarm.md`,
`docs/infra/reset-banco-vps.md` e `docs/infra/observability-local.md` (mesma lógica do
rename de dev local em `registro-trabalho.md`, seção 2026-08-19) — e este arquivo pode ser
apagado depois de executado, virando uma entrada de changelog em
`registro-trabalho.md`/`memoria-projeto.md` em vez de plano pendente.

## 5. Cortar: parar `registro`, migrar volumes, subir `geop`

```bash
ssh root@95.111.250.4
mkdir -p /opt/geop && cd /opt/geop
git clone <repo> .   # ou copiar docker-stack.yml + scripts já atualizados

docker stack rm registro
# esperar todos os serviços/tasks da stack antiga saírem
docker stack ps registro   # repetir até vir vazio

# passo 3 (migração de volumes) aqui, com a stack antiga já parada

cp /opt/registro/.env.prod /opt/geop/.env.prod   # mesmas variáveis, hosts já são geop.*
set -a; . ./.env.prod; set +a
docker stack config -c docker-stack.yml >/dev/null
docker stack deploy -c docker-stack.yml --with-registry-auth geop
```

## 6. Validar

```bash
docker service ls
docker service ps geop_api --no-trunc
docker service logs --tail 100 geop_api
curl -fsS "https://${REGISTRO_API_HOST}/api/v1/health"
```

Testar login, um fluxo de negócio simples e — como esta mudança nasceu de um pedido pra
"garantir a integração com o erp" — repetir manualmente uma sincronização real pelo widget
do erpsolid (`/integrations/erpsolid/contracts` e `/employee-payslips`) e confirmar `200`.

## 7. Limpeza (só depois de confirmar que `geop` está estável há alguns dias)

```bash
rm -rf /opt/registro
docker secret rm registro_postgres_password registro_database_url registro_jwt_secret \
  erpsolid_integration_key erpsolid_sso_shared_secret registro_s3_access_key registro_s3_secret_key
docker volume rm registro-postgres-data registro-minio-data registro-redis-data registro-backups
```

Apagar pacotes antigos no GHCR (`icarosimoes/registro/*`) é manual pela UI do GitHub — não
tem comando de CLI padrão pra isso.

## Rollback

Enquanto `/opt/registro` e os volumes/secrets antigos não forem apagados (passo 7), voltar
atrás é só `docker stack rm geop` + `docker stack deploy -c /opt/registro/docker-stack.yml
--with-registry-auth registro` de novo — nenhum dado foi destruído até a limpeza final.
