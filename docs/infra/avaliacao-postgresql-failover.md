# Avaliação — PostgreSQL com failover

Referente ao item **[M15]** de `docs/backlog.md` (auditoria 2026-06-22).

## Situação atual

- Um único container `postgres:17-alpine` no `docker-stack.yml`, `replicas: 1`, fixo no node manager.
- Backup diário via `pg_dump -Fc` (RPO 24h, retenção 14 dias) — ver `docs/infra/backup-restore.md`.
- Sem streaming replication, sem standby, sem failover automático.
- Se o container ou o node manager cair, a API fica fora do ar até restart manual ou reagendamento do Swarm no mesmo node (o volume é local, não replicado — um node novo não teria os dados).

## Opções consideradas

| Opção | RTO estimado | Complexidade | Custo | Observação |
|---|---|---|---|---|
| **Manter como está** (status quo) | horas (restore manual) | nenhuma | nenhum | Aceitável enquanto o volume de tenants/tráfego for baixo e houver tolerância a uma janela de indisponibilidade. |
| **Streaming replication (standby) self-hosted** | minutos (failover manual ou com Patroni/repmgr) | alta — requer 2º node, orquestração de failover, promoção de réplica, atualização de `DATABASE_URL` | infra de +1 node | Ganho real só aparece com múltiplos nodes Swarm; hoje a stack roda em node único, então a réplica teria que ser externa (outra VPS), aumentando a superfície operacional. |
| **Managed PostgreSQL** (RDS, Neon, Supabase, Crunchy, etc.) | segundos a minutos (failover automático do provedor) | baixa para o time (delegada ao provedor) | recorrente, escala com uso | Resolve failover, backup e patching automaticamente, mas contraria a decisão atual de self-host (MinIO já é self-hosted por design — ver [[project_infra-storage]]) e muda o modelo de custo de CAPEX de VPS para OPEX por uso. |

## Recomendação

Não implementar failover agora. Justificativa:

1. A stack roda em **single-node Swarm** — replicar o Postgres sem um segundo node não resolve o ponto único de falha real (o node em si), só adiciona complexidade.
2. O RPO/RTO atuais (24h / 1h, ver `backup-restore.md`) já foram formalmente aceitos como meta de disponibilidade do produto.
3. Failover de verdade (RTO em minutos) exige infraestrutura multi-node, o que é uma decisão maior de arquitetura de infra — não uma tarefa isolada de backend.

## Gatilho para reabrir esta avaliação

Reavaliar quando **qualquer** destes ocorrer:
- Provisionamento de um segundo node de infra (VPS adicional) para o Swarm.
- SLA contratual de disponibilidade exigir RTO menor que 1h.
- Volume de tenants/tráfego tornar uma indisponibilidade de horas inaceitável para o negócio.

Quando isso acontecer, a opção mais simples de implementar primeiro é streaming replication assíncrona (WAL shipping) para um standby manual, antes de investir em orquestração automática (Patroni/repmgr) ou migração para managed DB.
