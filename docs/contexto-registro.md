# Contexto do Registro

## O que e

O **Registro** e um SaaS de gestao operacional hoteleira. Ele centraliza todas as rotinas do dia a dia de um hotel — ordens de servico (ocorrencias e manutencao corretiva/preventiva em uma unica tela, com Kanban e visao em lista), solicitacoes fiscais, inspecoes, reunioes, passagem de turno, checklists, estoque e diario de obra — em uma unica plataforma web acessivel de qualquer dispositivo.

O sistema substitui um ERP legado (Aero, construido em Laravel/Vue) por uma stack moderna, nascendo multitenant para atender multiplos hoteis com isolamento completo de dados.

## Para quem serve

- **Gestores hoteleiros** que precisam acompanhar a operacao em tempo real: o que esta pendente, quem e responsavel, qual o prazo.
- **Equipes operacionais** (recepcao, governanca, manutencao, A&B, seguranca) que abrem e tratam ordens de servico, passam turno e executam checklists.
- **Financeiro/fiscal** que recebe solicitacoes de notas fiscais da recepcao com SLA controlado.
- **Operadores da plataforma** (admin SaaS) que gerenciam tenants, planos e assinaturas.

## Problema que resolve

Hoteis tipicamente operam com processos fragmentados — planilhas, cadernos, WhatsApp, sistemas isolados por departamento. Isso gera:

- Perda de informacao entre turnos
- Falta de rastreabilidade (quem fez o que, quando)
- SLAs nao monitorados
- Dificuldade de visao gerencial consolidada
- Retrabalho e comunicacao ineficiente

O Registro unifica tudo em um sistema unico com auditoria completa, notificacoes multicanal (in-app, e-mail, WhatsApp) e controle de acesso granular.

## O que o sistema faz

### Modulos operacionais

| Modulo | Funcao |
|---|---|
| **Dashboard** | Visao consolidada com KPIs, tendencias 7 dias e atividades recentes |
| **Ocorrencias** | Registro, tratativa e acompanhamento de eventos operacionais |
| **Solicitacoes fiscais** | Pedidos da recepcao ao financeiro com SLA em horario comercial |
| **Ordens de servico** | Workflow de 5 estados com Kanban visual e drag-and-drop |
| **Manutencao corretiva** | Registros avulsos de manutencao com prioridade, local e responsavel |
| **Manutencao preventiva** | Planos recorrentes (diario a anual) que geram OS automaticamente |
| **Checklists** | Templates reutilizaveis com execucao automatica e acompanhamento item a item |
| **Reunioes** | Agendamento com pautas, participantes e ata |
| **Relatorios de turno** | Passagem de turno estruturada com indicadores e observacoes por setor |
| **Pendencias de turno** | Comunicacao entre turnos com confirmacao de leitura e resolucao |
| **Inspecoes** | Check suites, inspection suites, vistorias de apartamento e auditorias (4 dominios dedicados na API) |
| **Diario de obra** | Registro diario de atividades, equipes, equipamentos e observacoes de obra |
| **Procedimentos** | Documentos operacionais com anexos |
| **Mural** | Avisos e comunicados para a equipe |
| **Estoque** | Controle de materiais com entrada/saida/ajuste vinculaveis a OS |
| **Cadastros** | Setores, locais, funcoes e dados do estabelecimento |
| **Perfis de acesso** | Gestao de roles com permissoes granulares por modulo |
| **Configuracoes** | Preferencias do tenant, integracoes (Brevo, Evolution API) |
| **Minha conta** | Perfil do usuario (nome, telefone, senha) |

### Capacidades transversais

- **Auditoria completa**: toda mutacao gera evento imutavel com diff campo a campo
- **Notificacoes multicanal**: in-app, e-mail (Brevo) e WhatsApp (Evolution API)
- **Anexos**: upload para MinIO (S3-compatible) com validacao de tipo, tamanho e quantidade
- **Timeline/tratativa**: historico de conversa em estilo ticket em todos os registros
- **Controle de acesso**: 35 permissoes, perfis por empresa, wildcard para admin
- **Exportacao**: CSV em todos os modulos
- **Integracao Chess Hotel**: solicitacoes fiscais recebidas automaticamente do ERP legado

### Plataforma SaaS

- Painel administrativo separado para gestao de tenants
- Planos, assinaturas e faturas com lifecycle (trial → ativo → inadimplente → suspenso)
- Integracao Asaas para cobranca automatica
- Metricas da plataforma (empresas, MRR, inadimplencia)

## Stack tecnica

| Camada | Tecnologia |
|---|---|
| API | Python 3.12, FastAPI, SQLAlchemy 2 async, Alembic, PostgreSQL 17 |
| Web (tenant) | Next.js 16, TypeScript, Tailwind CSS, App Router, Server Actions |
| Admin (plataforma) | Next.js 16 em dominio separado |
| Banco | PostgreSQL 17 com Row-Level Security (asyncpg) |
| Storage | MinIO self-hosted (S3-compatible) |
| Cache | Redis com TTL e invalidacao por tenant |
| Infra | Docker Compose (dev), Docker Swarm (prod), Traefik, GHCR |

## Isolamento e seguranca

- **Row-Level Security** no PostgreSQL: toda tabela com `company_id` tem policy RLS ativa — um tenant nunca ve dados de outro, mesmo em caso de bug na aplicacao.
- **JWT com refresh**: access token (30min) + refresh token (7 dias), cookies httpOnly.
- **Rate limiting**: endpoints sensiveis protegidos por slowapi.
- **Soft delete**: registros nunca sao removidos fisicamente.

## Origem e contexto

O Registro nasceu como sistema interno do **Aero Hotel** (Florianopolis/SC), operado pela Solid SD. O sistema legado (Chess Hotel) e um ERP hoteleiro em Laravel/Vue que continua em operacao durante a migracao gradual (estrategia strangler). O Chess Hotel se conecta ao Registro via integracao de API para enviar solicitacoes fiscais.

A decisao de transformar o Registro em SaaS comercial veio da percepcao de que outros hoteis enfrentam os mesmos problemas operacionais e nao possuem ferramentas adequadas.

## Numeros atuais

- 27+ dominios implementados na API
- 25+ tabelas com RLS ativo
- 35 permissoes granulares
- 70+ testes automatizados
- Producao ativa em `registro.solidsd.com.br`
