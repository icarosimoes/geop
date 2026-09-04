---
name: geop-backlog
description: Skill de metodologia para escrever/atualizar o backlog técnico (`docs/backlog.md`) do GEOP no padrão "engenheiro de software delegando pro time" — verificar status contra o código real antes de reportar (nunca confiar cegamente no que já está escrito), mapear gaps contra uma referência (legado Laravel/Vue, spec, protótipo), e escrever itens com nível de detalhe implementável sem re-investigação (arquivo exato, model/migration, contrato de endpoint, padrão existente a espelhar, critério de aceite). USE ao atualizar `docs/backlog.md`, ao comparar o GEOP contra o sistema legado ou uma referência externa pra achar o que falta, ou quando o usuário pede "atualiza o backlog", "detalha pra equipe implementar", "documenta os gaps", "vê o que está pendente".
---

Portado de `~/dev/erpsolid/.claude/skills/jarvis-backlog/` (mesma disciplina, adaptada ao
GEOP). Missão: manter `docs/backlog.md` como fonte de verdade **verificada contra o
código**, não uma lista de intenções que atrasa em relação ao que já foi entregue — e,
quando aparece um item novo, escrevê-lo pronto pra qualquer um pegar e implementar sem
reabrir o codebase pra entender o que fazer.

O GEOP já pratica boa parte disso organicamente (`docs/backlog.md` organizado por sprints
`P1`-`P17`, cada item fechado cita arquivo/migration/commit) — esta skill formaliza a
disciplina pra não perder o hábito conforme o arquivo cresce, e cobre o passo que mais
falha na prática: revisitar itens **antigos** ao mexer em itens novos vizinhos.

---

## Quando usar

- Ao atualizar `docs/backlog.md` depois de uma entrega (fim de feature/sprint).
- Ao comparar o GEOP contra uma referência externa — o legado Laravel/Vue (`docs/v1/`,
  `docs/legado/`, `docs/oportunidades-legado-operacao.md`), um protótipo visual, ou pedido
  de cliente — pra achar o que falta.
- Ao receber um pedido tipo "vê o que está pendente", "detalha pra implementar", "cria os
  itens", "documenta os gaps".

**Não usar** só pra registrar uma ideia solta de 1 linha — a disciplina de verificação
cruzada + detalhamento técnico compensa em itens de sprint/feature, não em notas avulsas.

---

## Passo 1 — Nunca confie no status já escrito

Antes de mudar, remover ou reafirmar o status de qualquer item existente (`[x]` ou `[ ]`),
**verifique contra o código real** — grep de rota/model/componente, não releitura do texto
anterior. `docs/backlog.md` é escrito sob pressão de tempo (por humanos e por você em
sessões passadas); ele atrasa em relação ao código com mais frequência do que parece.

Checklist mínimo por item que você for tocar:
1. O endpoint/rota existe? (`grep -n "@router\." api/app/domain/*/router.py`)
2. O model/coluna existe? (`grep -n "class X" api/app/models/`)
3. A tela consome isso de fato, ou só existe no backend sem UI (`web/`/`admin/`)?
4. Se o item cita arquivo/linha específicos, ainda batem? Código muda de lugar — uma
   referência desatualizada é pior que nenhuma.

> Caso real (2026-09-04, nesta sessão): o item "`save_brevo`/`save_evolution` retornam
> `has_credentials: true` incondicionalmente" estava marcado `[ ]` em `docs/backlog.md`.
> Um `grep -n "has_credentials=bool" api/app/domain/settings/router.py` achou o fix já em
> produção desde a PR #19. Sem esse grep, o item ficaria "pendente" pra sempre.

Se a verificação confirmar o que já estava escrito, não precisa reescrever nada. Se **não**
bater, corrija o status e **cite a evidência** (arquivo:linha, PR, migration) em vez de só
trocar o `[ ]`/`[x]` — quem ler depois precisa poder reverificar sem repetir sua investigação.

---

## Passo 2 — Comparar contra uma referência (gap analysis)

Quando o pedido é "vê o que falta comparando com X" (legado, spec, sistema de referência):

1. Compare **feature por feature**, não a impressão geral — pra cada tela/fluxo da
   referência, grep no GEOP por rota/model/componente equivalente antes de concluir
   "não existe". Ausência de resultado é a evidência de gap, não "não lembro de ter visto".
2. Separe 3 categorias de resultado, porque cada uma vira um item diferente:
   - **Ausente de verdade** (zero rota/model/tela) → item do zero.
   - **Backend pronto, falta só UI** (ou vice-versa) → item menor, aponte o que já existe
     pra não ser refeito.
   - **Existe mas divergente** (versão simplificada onde a referência pede mais) → não
     risque o item existente como errado; anote que cobre uma versão parcial.
3. Referência de trabalho já feito assim: `docs/oportunidades-legado-operacao.md` (P15/P16
   do backlog nasceram de comparar o GEOP contra `docs/aero-main`, achados classificados em
   "vira item" vs. "já tem equivalente, sem ação").

---

## Passo 3 — Escrever o item no nível "engenheiro delegando pro time"

Um item pronto pra implementar sem re-investigação responde, no mínimo:

- **Arquivo(s) exato(s)** a criar ou tocar — caminho completo (`api/app/domain/x/service.py`),
  não "no backend".
- **Padrão existente a espelhar** — aponte um domínio irmão já implementado ("mesmo padrão
  de `contracts/service.py::_generate_contract_number`") em vez de descrever a estrutura do
  zero; mais curto e garante consistência de convenção automaticamente.
- **Contrato de dado**, quando não-trivial — shape de migration, campos de request/response.
- **Critério de aceite** implícito ou explícito.
- Segue o formato já usado no arquivo: checklist `- [ ]`/`- [x]` agrupado por seção
  numerada (`P1`, `P2`, ... `P17`), não tabela de ID — mantenha a convenção existente, não
  introduza um formato novo no mesmo arquivo.

---

## Passo 4 — Rastreabilidade de itens obsoletos/movidos

Quando um item antigo é substituído por um mais detalhado, ou quando uma feature inteira é
removida (já aconteceu duas vezes no GEOP: Conferência de Discrepâncias e Solicitações
Fiscais, ambas em 2026-08-31), **não apague o histórico silenciosamente** — mantenha a
entrada da seção original explicando o que foi removido e por quê (o próprio
`docs/backlog.md` já faz isso bem nessas duas seções; siga o mesmo padrão).

---

## Como você opera

1. Antes de escrever um item novo, releia a seção do backlog em que ele vai entrar — evita
   duplicar algo que já existe com outro nome.
2. Rode o Passo 1 (verificação contra código) em qualquer item que for tocar, não só nos
   novos — é comum achar status desatualizado de itens vizinhos.
3. Prefira apontar um padrão existente a descrever uma estrutura nova do zero.
4. Feche citando a evidência (arquivo:linha, PR, migration) de qualquer mudança de status.

## Checklist de auditoria de backlog

- [ ] Todo item com status alterado tem evidência citável (arquivo:linha, PR, migration)
- [ ] Todo item novo aponta um arquivo/caminho exato, não "no backend"/"no frontend" genérico
- [ ] Todo item novo cita um padrão existente a espelhar, quando houver análogo
- [ ] Item substituído/obsoleto está anotado com o motivo, não apagado silenciosamente
- [ ] Formato do item novo segue a convenção já usada na seção (checklist por sprint `P*`)
