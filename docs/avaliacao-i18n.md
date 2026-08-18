# Avaliação — Internacionalização (i18n)

Referente ao item **[L3]** de `docs/backlog.md` (auditoria 2026-06-22).

## Situação atual

- Todo texto de UI (`web/` e `admin/`) está hardcoded em português, direto nos componentes.
- Domínio de negócio é gestão operacional no Brasil, hoje usado majoritariamente por hotéis (ver contexto do produto em `docs/contexto-registro.md`): ocorrências, solicitações fiscais brasileiras (CPF/CNPJ).
- Não há indício, no backlog ou na documentação do produto, de plano de expansão para operação fora do Brasil ou para tenants que exijam outro idioma.
- Conceitos centrais do domínio são específicos do mercado brasileiro (CPF/CNPJ, CEP, regras fiscais de solicitações) — internacionalizar a UI sem internacionalizar essas regras de negócio teria valor limitado.

## Opções consideradas

| Opção | Esforço | Quando faria sentido |
|---|---|---|
| **Não fazer nada agora** | zero | Enquanto todos os tenants forem operações no Brasil em português. |
| **`next-intl` com só pt-BR** | baixo, mas sem retorno imediato | Preparar terreno antes de uma expansão confirmada, evitando retrabalho maciço depois. |
| **`next-intl` com pt-BR + outro idioma** | alto (~8h+ só extração de strings, mais tradução e QA) | Quando houver um tenant/mercado concreto exigindo outro idioma. |

## Recomendação

Não implementar agora. Não há sinal de demanda real (nenhum tenant, prospect ou requisito de negócio pedindo outro idioma) e o custo de extrair todas as strings hardcoded (~8h+ estimado no backlog, provavelmente mais dado o volume de módulos) não se paga sem um caso de uso concreto.

## Gatilho para reabrir esta avaliação

Reavaliar quando houver um tenant ou mercado concreto que exija operação em outro idioma. Nesse momento, considerar `next-intl` (compatível com App Router/Server Components do Next.js 16) e planejar a extração de strings como projeto dedicado, não como tarefa incremental — o volume de texto hardcoded hoje é grande o suficiente para justificar um levantamento módulo a módulo antes de começar.
