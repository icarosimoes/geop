# Agentes Jarvis do GEOP

Regras adaptadas da referência Aloji em `/home/icarosimoes/dev/aloji/docs/agentes`. Este diretório é a cópia aplicável e versionada do GEOP; prevalece sobre referências externas quando houver diferença de domínio.

- [Engenharia](jarvis-engenharia.md): arquitetura, qualidade e entrega.
- [Layout e CRUD](jarvis-layout-crud.md): telas, estados e acessibilidade.
- [Performance](jarvis-performance.md): Next.js, API e banco.
- [Segurança](jarvis-seguranca.md): autenticação, secrets e supply chain.
- [SaaS/multiempresa](jarvis-saas.md): `company_id` e futura RLS.
- [Asaas](jarvis-asaas.md): cobrança, webhooks e reconciliação financeira.

Financeiro operacional, reservas, Channex e CRM continuam fora do escopo. Asaas entra somente como cobrança da plataforma SaaS; sandbox já ativo (ver `jarvis-asaas.md`), produção ainda pendente dos itens em aberto na seção "Operação" desse arquivo.

## Skills do Claude Code (`.claude/skills/geop-*`, desde 2026-09-04)

Estes documentos são a camada de **princípios condensados** (curados manualmente, sem
gatilho automático). Desde 2026-09-04 existe uma segunda camada, mais operacional, em
`.claude/skills/` — Skills reais do Claude Code que **disparam automaticamente** pelo
`description` no frontmatter (sem precisar que alguém abra o arquivo), com comandos
prontos pra copiar, referências de arquivo:linha e o histórico de incidentes reais do
GEOP que motivou cada regra. Nasceram de revisar os agentes/skills equivalentes de
`~/dev/erpsolid` e `~/dev/aloji` e trazer só o que se aplica à arquitetura real do GEOP
(nunca copiado sem verificar contra o código):

| Skill | Substitui/complementa | Cobre |
|---|---|---|
| `geop-saas` | `jarvis-saas.md` (mais detalhado) | RLS com 3 roles Postgres, GUC `app.current_company_id`, painel admin, billing da plataforma |
| `geop-performance` | `jarvis-performance.md` (mais detalhado) | Server Components vs Client, Promise.all, agregação SQL, N+1 |
| `geop-seguranca` | `jarvis-seguranca.md` (mais detalhado) | Protocolo de auditoria de CVE/supply chain, recuperação pós-incidente |
| `geop-infra` | (novo, sem equivalente aqui) | Manutenção de disco e recuperação de deploy no Docker Swarm de produção |
| `geop-backlog` | (novo, sem equivalente aqui) | Metodologia pra manter `docs/backlog.md` verificado contra o código |

**Não portados** (avaliados e descartados — domínio inexistente no GEOP): `jarvis-financeiro`
(GEOP não tem Payables/Receivables/DRE), `jarvis-asaas`/`jarvis-channex`/
`jarvis-motor-reservas`/`jarvis-crm` do Aloji (motor de reservas, channel manager e CRM de
hóspede não existem aqui — o Asaas do GEOP é só cobrança da própria assinatura SaaS, já
coberto por `jarvis-asaas.md` acima), `jarvis-layout-crud` do erpsolid (arquitetura de
frontend incompatível: erpsolid usa Client Component + `actions.ts` único por projeto; o
GEOP usa Server Component real + `actions.ts` por feature — `jarvis-layout-crud.md` já
documenta o padrão certo do GEOP), `jarvis-teste-e2e` do erpsolid (script de auditoria de
ponta a ponta específico do domínio financeiro do erpsolid; candidato a adaptar no futuro
pro módulo comercial do GEOP — orçamento/venda/fatura/pagamento — se houver demanda).
