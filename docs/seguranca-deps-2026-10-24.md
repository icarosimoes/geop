# Atualização de dependências por CVE — 2026-10-24

> Registro da varredura `npm audit` feita em todos os projetos de `~/dev` em 2026-10-24. Complementa o histórico do guia Jarvis de segurança, quando o projeto tem um.

## O que foi feito
- `web`, `colaborador`, `admin`: `npm audit fix`. `npm audit` = 0 nos três; `next build` passou.
- `web`: `zod` 3 → `^4.6.6`. Único ajuste necessário: `z.record(z.object(...))` virou `z.record(z.string(), z.object(...))` em `lib/schemas.ts`.
- `colaborador`: `zod` removido (não era importado em lugar nenhum).
- Commit `2cfb32d4`.

## Pendente
- Nada.
