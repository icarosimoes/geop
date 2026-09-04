---
name: geop-infra
description: Skill de manutenção conservadora de espaço em disco e recuperação de deploy parcial na VPS Docker Swarm do GEOP (stack `registro`, diretório `/opt/registro`). Use para diagnosticar "no space left on device", limpar containers Exited/Dead sem tocar em volumes, e recuperar um deploy que ficou com serviços em SHAs misturados. TRIGGER quando o usuário menciona "sem espaço", "no space left", "docker prune", "limpar VPS", "deploy travado", "serviço não converge".
---

Portado de `~/dev/aloji/.claude/agents/jarvis-infra-disco.md`, adaptado à topologia real do
GEOP (`docs/infra/deploy-swarm.md`, `docs/infra/runbook-producao.md`).

## Identidade operacional do GEOP em produção

| Item | Valor |
|---|---|
| Diretório na VPS | `/opt/registro` |
| Nome do stack Swarm | `registro` (renomear para `geop` ainda pendente — ver `docs/infra/renomear-stack-producao.md`) |
| Serviços | `registro_api`, `registro_web`, `registro_admin`, `registro_colaborador`, `registro_db`, `registro_redis`, `registro_minio`, `registro_backup` |
| Imagens | `ghcr.io/icarosimoes/geop/api`, `/web`, `/admin`, `/colaborador` — tag imutável `sha-<GITHUB_SHA completo>` |
| Hosts | `geop.solidsd.com.br` (web), `api.geop.solidsd.com.br`, `painel.geop.solidsd.com.br` (admin), `colaborador.geop.solidsd.com.br` |
| Health check | `curl -fsS https://api.geop.solidsd.com.br/api/v1/health` e `/health/ready` (`ready` confirma acesso ao banco; `health` sozinho não) |
| Proxy | Traefik na rede overlay `traefik-public` |

A VPS pode hospedar outras stacks além do `registro` — **nunca assuma que um container fora
do prefixo `registro_` pode ser removido** sem confirmar o que é antes.

## Regra de ouro

Nunca execute limpeza destrutiva de volumes em produção. Proibido sem autorização humana
explícita **e** backup validado:

```bash
docker volume prune
docker system prune --volumes
rm -rf /var/lib/docker/volumes
docker stack rm registro
```

Volumes contêm Postgres (`registro_db`), uploads (MinIO), backups — dados que não voltam
sem restore.

## Diagnóstico inicial (não altera estado)

```bash
df -h /
df -ih /
docker service ls --format '{{.Name}} {{.Replicas}} {{.Image}}' | grep '^registro_' | sort
docker ps -a --filter status=exited --filter status=created --filter status=dead \
  --format '{{.ID}} {{.Names}} {{.Status}}' | head -100
timeout 20 docker system df || echo docker_system_df_timeout
```

Se `docker system df` travar, use `du` com timeout em vez de insistir:

```bash
timeout 45 du -xhd1 /var/lib/docker 2>/dev/null | sort -h | tail -20 || echo timeout
timeout 45 du -xhd1 /var/lib/containerd 2>/dev/null | sort -h | tail -20 || echo timeout
```

## Limpeza segura padrão (não remove volumes)

```bash
echo "before"; df -h /
docker container prune -f       # remove Exited/Created/Dead
docker builder prune -af        # cache de build não usado
docker image prune -af          # imagens sem container usando
echo "after"; df -h /
```

## Deploy parcial (SHAs misturados entre serviços)

O workflow `Publish images` (`.github/workflows/publish.yml`) publica API/web/admin/
colaborador em paralelo e, depois, o job `deploy` conecta via SSH e atualiza os serviços
automaticamente com `--with-registry-auth` e `start-first`. Se faltar espaço durante o pull,
alguns serviços ficam no SHA novo e outros no antigo:

```bash
docker service ls --format '{{.Name}} {{.Replicas}} {{.Image}}' | grep '^registro_' | sort
docker service ps registro_api --no-trunc --format '{{.Name}} {{.CurrentState}} {{.Error}} {{.Image}}' | head -10
```

Se um serviço ficar com tasks `Rejected`/pausadas por falta de imagem, force só ele depois de
liberar espaço:

```bash
docker service update --with-registry-auth --force registro_api
```

Recuperação manual (pull explícito + reaplica o stack) — precisa das variáveis de
`/opt/registro/.env.prod`:

```bash
cd /opt/registro
set -a; . ./.env.prod; set +a

IMAGE_TAG=sha-<sha-completo>
docker pull ghcr.io/icarosimoes/geop/api:$IMAGE_TAG
docker pull ghcr.io/icarosimoes/geop/web:$IMAGE_TAG
docker pull ghcr.io/icarosimoes/geop/admin:$IMAGE_TAG
docker pull ghcr.io/icarosimoes/geop/colaborador:$IMAGE_TAG

env IMAGE_TAG=$IMAGE_TAG docker stack deploy -c docker-stack.yml --with-registry-auth registro
```

Depois, alinhar `IMAGE_TAG` em `.env.prod` pra não sofrer rollback acidental num próximo
deploy manual (já houve um incidente exatamente assim, ver `docs/registro-trabalho.md`,
2026-08-14 — "troca de domínio", `IMAGE_TAG` desatualizado no `.env.prod` quase causou
rollback):

```bash
cp .env.prod .env.prod.before-image-tag-$(date +%Y%m%d_%H%M%S)
sed -i "s/^IMAGE_TAG=.*/IMAGE_TAG=$IMAGE_TAG/" .env.prod
grep '^IMAGE_TAG=' .env.prod
```

## Validação pós-limpeza/deploy

```bash
docker service ls --format '{{.Name}} {{.Replicas}} {{.Image}}' | grep '^registro_' | sort
curl -fsS https://api.geop.solidsd.com.br/api/v1/health
curl -fsS https://api.geop.solidsd.com.br/api/v1/health/ready
df -h /
```

Estado esperado: `health`/`health/ready` retornam 200 com `cache: connected` (achado real,
2026-07-14: `registro_redis` em 0/1 réplicas não aparecia como erro em `health`, só
`health/ready` acusava `cache: unavailable`); serviços `registro_*` principais convergidos,
nenhum em `0/1`/`1/2` sem explicação.

### Serviço reagendado não reconecta sozinho — precisa de `--force` nos dois lados

Achado real (2026-07-14): `registro_redis` ficou em 0/1 réplicas por dias sem crash visível
nos logs (shutdown limpo, a réplica só nunca foi reagendada pelo Swarm — `Rejected`/"context
canceled"). `docker service update --force registro_redis` trouxe a réplica de volta, mas
`registro_api` continuou reportando `cache: unavailable` mesmo com o Redis já respondendo —
a conexão da API ficou presa no estado de falha anterior. Precisou de
`docker service update --force registro_api` também pra reconectar. **Ao recuperar um
serviço de infra (Redis/MinIO) que caiu, force também os serviços de aplicação que dependem
dele, não só o próprio.**

## Processos Docker presos

```bash
ps -eo pid,ppid,etime,stat,cmd | grep -E 'docker (image prune|system df)|du -xhd1' | grep -v grep
kill <pid-do-cliente>   # mata só o cliente, nunca o dockerd
```

Não reinicie `dockerd`/`containerd` durante um deploy em andamento.

## Limites de alerta

| Sinal | Ação |
|---|---|
| `/` ≥ 85% | Rodar diagnóstico e planejar limpeza |
| `/` ≥ 90% | Rodar limpeza segura padrão |
| `/` ≥ 95% | Bloquear deploy até liberar espaço |
| Livre < 20 GB | Limpar antes de pull/build |
| Containers `Dead` > 0 | `docker container prune -f` após conferir serviços |

## Mudança crítica — sempre seguir `docs/seguranca.md`

Qualquer reboot, rotação de credencial, alteração de volume/rede ou corte de domínio exige
backup novo, validação do artefato, plano de rollback e registro em
`docs/registro-trabalho.md` — a mesma regra de "Mudança crítica" já documentada em
`docs/seguranca.md`, não uma regra nova desta skill.
