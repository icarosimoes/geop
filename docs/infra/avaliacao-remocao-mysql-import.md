# Avaliação — Remoção do profile `mysql-import` e da dependência `asyncmy`

Referente ao item 12 de "Próximos passos pendentes" em `docs/backlog.md`, revisado após a descontinuação do corte final do V1 (2026-07-04, ver `docs/backlog.md` P5 e [[project_v1_cutover_discontinued]]).

## Situação atual

- `docker-compose.yml` define o service `mysql` sob `profiles: [mysql-import]` — só sobe com `docker compose --profile mysql-import up`, não impacta o dev loop padrão.
- `api/pyproject.toml` tem `asyncmy` como optional dependency (`mysql-import`), não instalada por padrão.
- O corte final de dados do V1 foi descontinuado — não há mais um evento único que "esgote" a utilidade deste profile.
- Scripts que dependem dele continuam existindo e documentados: `import_v1.py`, `api/scripts/migrate_v1_attachments.py`, com runbook em `docs/infra/importacao-legado.md`.

## Análise

Diferente do corte final (que era um evento único e planejado), este profile serve para **importações pontuais** — ex.: se em algum momento for necessário puxar um registro específico do V1 para conferência ou correção de dado histórico, sem depender de acesso direto ao MySQL de produção do Chess/V1.

Como o profile:
- não roda por padrão (opt-in explícito via `--profile`),
- não pesa na imagem de produção (fica fora do `docker-stack.yml`, é só para uso local/dev),
- e a dependência `asyncmy` é opcional (não entra no build padrão da API),

o custo de mantê-lo é baixo. O custo de removê-lo agora e precisar recriá-lo depois (se surgir necessidade pontual de consultar o V1) é maior que o custo de manutenção atual.

## Recomendação

Não remover agora. Manter o profile `mysql-import`, a dependência opcional `asyncmy` e os scripts de importação como estão — servem como ferramenta de consulta/importação pontual ao V1, independente do corte final (que está descontinuado).

## Gatilho para reabrir esta avaliação

Remover quando o V1 (Laravel) for oficialmente desligado/descomissionado como sistema de referência — nesse ponto não haverá mais nenhum dado "fonte" no MySQL para consultar pontualmente, e o profile perde sua última utilidade.
