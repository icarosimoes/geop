# Avaliação — Replicação do MinIO

Referente ao item **[M18]** de `docs/backlog.md` (auditoria 2026-06-22).

## Situação atual

- Um único container `minio` (modo standalone, não distribuído) no `docker-stack.yml`, `replicas: 1`, fixo no node manager, volume local `registro-minio-data`.
- Backup diário via `mc mirror --overwrite` para `/backups/minio` (mesmo host) — ver `docs/infra/backup-restore.md`. Não é um espelho em tempo real, é um snapshot diário.
- Anexos (`attachments`, avatares) dependem inteiramente deste único volume. Perda do disco = perda dos arquivos até o último backup diário.
- Infra self-hosted por decisão de produto (ver [[project_infra-storage]]) — não usar cloud S3.

## Opções consideradas

| Opção | Proteção contra | Complexidade | Observação |
|---|---|---|---|
| **Manter como está** (backup diário local) | Corrupção de arquivo, erro humano (delete acidental recuperável do snapshot) | nenhuma | Não protege contra falha de disco/node — o backup fica no mesmo host. |
| **MinIO em modo distribuído/erasure coding** (múltiplos nodes/discos) | Falha de disco individual, sem downtime | alta — exige no mínimo 4 nodes/discos para erasure coding eficaz | Requer redesenhar a infra para multi-node; não cabe na VPS única atual. |
| **`mc mirror` para storage externo** (outra VPS ou bucket S3 de terceiro só para backup, não para servir tráfego) | Falha total do node de produção | baixa-média — reusa o `mc mirror` já existente, só muda o destino | Caminho mais barato: não muda a arquitetura de serving, só tira a cópia de backup do mesmo host físico. |
| **Migrar para S3 gerenciado** | Falha de disco, de node, durabilidade 99.999999999% | baixa para o time, mas contraria decisão de self-host | Fora de escopo dado o requisito de self-host. |

## Recomendação

Não implementar clustering do MinIO agora — o ganho não compensa a complexidade de operar múltiplos nodes na infra atual (single VPS/manager). O risco real hoje não é "disco cheio" ou "nó do MinIO caiu", é **backup e volume de produção morarem no mesmo host físico**.

Ação de menor esforço com maior redução de risco, quando priorizada: apontar o `mc mirror` do serviço `backup-minio` para um destino fora do host de produção (outra VPS via SSH/rsync, ou um bucket S3 externo dedicado só a backup — não a servir tráfego). Isso não está implementado hoje e fica registrado como item futuro, não como clustering.

## Gatilho para reabrir esta avaliação

Reavaliar clustering/erasure coding quando a infra crescer para múltiplos nodes por outros motivos (ex: failover de Postgres, ver `avaliacao-postgresql-failover.md`) — nesse cenário, distribuir o MinIO nos mesmos nodes passa a ter custo marginal baixo.
