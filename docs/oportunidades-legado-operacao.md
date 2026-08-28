# Oportunidades identificadas no legado

## Objetivo

Registrar as capacidades úteis encontradas em `docs/aero-main` e orientar a evolução do GEOP sem copiar a implementação Laravel. O legado é evidência funcional; os contratos, regras de isolamento, auditoria e UX devem seguir a arquitetura atual do GEOP.

## Fontes analisadas

- `docs/aero-main/app/DiscrepancyReport.php`: conferência diária por unidade, códigos operacionais, resumo e normalização de dados.
- `docs/aero-main/app/Http/Controllers/Event/DiscrepancyReport/DiscrepancyReportController.php`: CRUD, exportações PDF/Excel e listagem paginada.
- `docs/aero-main/app/Services/Indicators/MonthlyIndicatorsService.php`: indicadores mensais, fechamento, saldo de caixa, métricas derivadas e exportação anual.
- `docs/aero-main/app/AuditReportFinanceCashItem.php`: conferência por forma de pagamento.
- `docs/aero-main/app/AuditReportFinanceDivergenceItem.php`: divergências financeiras, valor, providência, anexo e resolução.
- `docs/aero-main/app/Models/FinancialRequest.php`: histórico, participantes, anexos e estados de solicitações financeiras.
- `docs/aero-main/app/Models/DocumentRecord.php` e `DocumentType.php`: controle de documentos com vencimento (alvará, licença, certidão, apólice, contrato), status calculado e histórico de anexos por substituição.

## Ordem de execução

### 1. Conferência operacional de discrepâncias

**Prioridade:** alta  
**Estado:** primeiro vertical slice entregue (2026-08-28) — domínio `discrepancy_reports`.  
**Entregue:** migration (tabela + RLS + permissões), model, schemas Pydantic, service, router (CRUD + PDF via reportlab), tela `/conferencias` (listagem paginada com filtro por data/status, formulário com grade de locais e busca de responsáveis), 8 testes cobrindo CRUD, resumo por código, local duplicado, fechamento, isolamento cross-tenant e permissão.  
**Pendente:** códigos configuráveis por tenant (a v1 aceita string livre até 40 caracteres, sem catálogo); caminho de reabertura de conferência fechada (hoje `closed` bloqueia qualquer PATCH, inclusive voltar o status); exportação em Excel; timeline/anexos (o domínio ainda não usa `record_event` para anexos nem os serviços de attachment existentes).

A conferência registra, para cada unidade/local, duas classificações operacionais, observações e o responsável pela preparação, conferência e recebimento. No legado, a grade era específica para apartamentos; no GEOP, o modelo deve aceitar qualquer `Location` ou unidade operacional e usar códigos configuráveis por tenant.

**Contrato mínimo:**

- data da conferência;
- local/unidade;
- código da primeira verificação;
- código da segunda verificação;
- observações;
- responsáveis e timestamps;
- estado `draft`, `submitted` ou `closed`;
- resumo calculado por código;
- timeline e anexos via os serviços existentes.

**Critérios de aceite:**

- toda leitura e mutação filtra `company_id` e respeita RLS;
- códigos inválidos são rejeitados pelo schema Pydantic;
- fechamento impede edição comum e registra auditoria;
- o resumo é calculado no servidor, sem confiar no frontend;
- listagem possui paginação, filtro por data/local/status e exportação limitada;
- tenant sem unidades cadastradas recebe estado vazio orientativo;
- testes cobrem CRUD, validação, fechamento, permissão e cross-tenant.

**Fora de escopo inicial:** integração com PMS, códigos nacionais de hotelaria, sincronização em tempo real e aplicativo mobile dedicado.

### 2. Indicadores mensais de gestão

**Prioridade:** alta  
**Estado:** planejado  
**Dependência:** definição do conjunto de indicadores e permissões de fechamento.

O legado mantém uma competência mensal por ano, calcula campos derivados e transporta o saldo de caixa do mês anterior. O GEOP deve tratar os indicadores como uma capacidade de gestão configurável, com valores monetários em `Decimal`/centavos e sem acoplar a campos exclusivos de hotelaria.

**Primeiro recorte:** competência, receita, custos, despesas, entradas/saídas de caixa, saldo inicial/final, status de fechamento, responsável e exportação anual.

**Critérios de aceite:**

- uma competência única por tenant, ano e mês;
- mês fechado não pode ser alterado sem permissão específica;
- saldo inicial pode ser herdado do mês anterior, com ajuste auditado;
- valores derivados são calculados no backend;
- dados ficam isolados por tenant e possuem auditoria;
- importação/exportação tem validação e limite explícitos;
- testes cobrem reabertura, competência duplicada, cálculos e isolamento.

**Fora de escopo inicial:** contabilidade oficial, emissão fiscal, conciliação bancária automática e integração com ERP.

### 3. Conferência financeira de auditorias

**Prioridade:** média-alta  
**Estado:** planejado  
**Dependência:** primeira versão de auditorias e permissões financeiras.

A auditoria financeira do legado separa conferência de caixa e divergências, permitindo registrar forma de pagamento, valor, evidência, providência e resolução. Deve ser uma extensão do domínio de auditorias atual, não uma duplicação de solicitações fiscais.

**Primeiro recorte:** itens de caixa, divergências, responsável, status, valor, observação, anexo e aprovação/encerramento.

**Critérios de aceite:**

- cada item pertence à auditoria e ao tenant;
- divergências possuem estado e responsável explícitos;
- valores usam `Decimal` e não `float`;
- alterações, anexos e encerramento entram na timeline;
- permissões separam visualizar, lançar e resolver;
- relatório mostra totais e divergências abertas;
- testes cobrem autorização, valores, anexos e cross-tenant.

### 4. Capacidades opcionais do legado

Estas capacidades só devem entrar após validação com clientes fora da hotelaria:

- formulários configuráveis e versionados;
- relatórios de perdas não justificadas;
- abastecimento de alimentos e bebidas;
- relatórios específicos de quartos e governança.

Elas não devem entrar como tabelas ou regras obrigatórias do núcleo do GEOP.

### 5. Controle de documentos com vencimento

**Prioridade:** alta (agnóstico de segmento, baixo esforço)  
**Estado:** planejado  

O legado mantém tipos de documento configuráveis por tenant (`DocumentType`: nome + slug único) e registros (`DocumentRecord`) com órgão emissor, data de emissão, data de vencimento e alerta configurável em dias. O status não é armazenado — é calculado no servidor a partir de hoje, da presença de anexo e do vencimento: `pending_attachment` → `current` → `expiring_soon` → `overdue` → `no_expiration`. Cada novo anexo substitui o atual e o anterior fica em histórico (`superseded_at`), dando versionamento sem tabela extra.

Isso serve qualquer tenant com alvará, licença, certidão, apólice ou contrato para acompanhar — nenhum cliente atual do GEOP tem hoje onde registrar isso.

**Primeiro recorte:**

- tipo de documento (cadastro simples, nome único por tenant);
- registro: tipo, órgão emissor, emissão, vencimento, alerta em dias, notas;
- anexo via o serviço de attachments existente (MinIO), com substituição preservando histórico;
- status calculado no servidor, nunca persistido;
- notificação de vencimento próximo via `notify_record_event` (reaproveitar, não recriar).

**Critérios de aceite:**

- toda leitura e mutação filtra `company_id`;
- exclusão de tipo de documento com registros vinculados é bloqueada ou exige confirmação explícita;
- status nunca é aceito do payload do cliente;
- timeline registra criação, atualização e troca de anexo;
- testes cobrem cálculo de status nas cinco variações, substituição de anexo e isolamento cross-tenant.

**Fora de escopo inicial:** aviso por e-mail/WhatsApp além do já existente em `notify_record_event`; assinatura eletrônica; integração com órgãos emissores.

## Decisões de arquitetura

- Não migrar código Laravel diretamente.
- Reaproveitar `service.py`, schemas Pydantic, ACL, RLS, `AuditEvent`, anexos MinIO e exportação existente.
- Preferir entidades dedicadas para dados consultados, filtrados ou fechados; usar JSON apenas para extensões realmente variáveis.
- Generalizar nomes do domínio: `location`/`unit` em vez de `room`/`apartment`.
- Atualizar `mapa.md`, `domain-model.md`, `api-reference.md`, `web-rotas-ui.md`, `backlog.md` e `registro-trabalho.md` junto com cada entrega.

## Próximo passo técnico

Com o vertical slice de `discrepancy_reports` entregue, o próximo passo é fechar as pendências listadas no item 1 (reabertura de conferência fechada, códigos configuráveis, timeline/anexos) ou avançar para o item 2 (indicadores mensais) ou o item 5 (controle de documentos), a depender de qual tiver mais tração com clientes.
