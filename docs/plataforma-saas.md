# Plataforma SaaS

## Estado implementado

O Compose sobe PostgreSQL 17 com RLS, MinIO, API, Web e Admin. Alembic executa migrations e seed fictício na primeira subida. O MySQL sobe apenas sob demanda via profile `mysql-import` para importação do dump V1.

| Componente | URL local | Responsabilidade |
| --- | --- | --- |
| Web do tenant | `http://localhost:3000` | produto Registro |
| API | `http://localhost:8000` | regras tenant e plataforma |
| Painel admin | `http://localhost:3001/login` | operação comercial cross-tenant |
| PostgreSQL | `localhost:5433` | banco principal com RLS |
| MinIO | `localhost:9000` (API), `localhost:9001` (console) | storage S3-compatible para anexos |

Credenciais de demonstração:

| Contexto | E-mail | Senha | Tenant |
| --- | --- | --- | --- |
| tenant (Aero Hotel) | `demo@aerohotel.local` | `Registro@123` | `aero-hotel` |
| tenant (demo) | `icaro@registro.local` | `Registro@123` | `empresa-demo` |
| tenant (demo) | `ana@registro.local` | `Registro@123` | `filial-teste` |
| plataforma | `admin@registro.local` | `RegistroAdmin@123` | não se aplica |

Essas credenciais são somente locais. Em produção o seed exige senhas fornecidas por secret/env e não exibe credenciais na interface.

## Isolamento

O login tenant recebe apenas e-mail e senha. Se o e-mail pertencer a um único tenant, entra direto. Se pertencer a mais de um, a API retorna `422 multi_tenant` com a lista de empresas para o front exibir um seletor; o segundo envio inclui `company_id`. O JWT carrega `company_id`, e a consulta revalida usuário, empresa, status e exclusão lógica. O token administrativo usa outro tipo, outro endpoint e outra tabela; não pode ser usado em `/auth/me`.

O PostgreSQL aplica RLS (Row-Level Security) em 24+ tabelas com `company_id`. O GUC `app.current_company_id` é setado via `SET LOCAL` na dependency `current_user`. Rotas platform (admin) operam como superuser com `BYPASSRLS`.

## Painel administrativo

O painel admin foi reescrito no padrão Jarvis/Aloji com Tailwind CSS 4, Lucide icons e Sonner (toasts). Funcionalidades implementadas:

- **Dashboard**: 4 stat cards (empresas, trial, inadimplentes, MRR) com dados reais da API `/platform/metrics`.
- **Empresas**: tabela com busca, badges de status (trial/ativo/inadimplente/suspenso/cancelado), menu de ações por assinatura (suspender/reativar/cancelar), modal de criação de tenant, delete com confirmação.
- **Planos**: cards com preço formatado em BRL, limites e status ativo/inativo.
- **Feature Flags**: CRUD de flags globais (`key`, `enabled_default`, `targeting_rules` em JSON), soft delete.
- **Usuários**: CRUD da equipe interna da plataforma (`PlatformUser`), com papéis `super_admin`/`support`/`billing`/`read_only`.
- **Suporte**: fila de pedidos abertos pelo botão de Ajuda do tenant (`web/`), com filtro por status (pendente/contatado/resolvido).
- **Uso**: consumo por tenant (usuários ativos, ocorrências do mês), agregado por métrica; snapshot gerado sob demanda (sem Celery no Registro).
- **Auditoria**: tabela de logs administrativos da plataforma (`platform_audit_logs`).
- **Auth**: Server Actions + httpOnly cookies.
- **API proxy**: route handler `/api/proxy/[...path]` para mutations client-side proxeadas para `/platform/*`.

Ver `docs/api-reference.md` (seção "Plataforma — feature flags, usuários, suporte e uso") para o contrato completo dos endpoints.

## Comercial e cobrança (implementado)

- CRUD auditado de tenants, planos e assinaturas — endpoints platform com POST/GET/PATCH/DELETE, todos auditados via `PlatformAuditLog`.
- Lifecycle: trial 14 dias → past_due (expiração) → suspended (7 dias de tolerância, bloqueia login) → reativação via endpoint admin.
- Asaas sandbox: `AsaasClient` async com httpx, webhook autenticado e idempotente (dedup via `webhook_events`), reconciliação periódica (`POST /platform/billing/reconcile`).

## Próximas capacidades

- Convite e recuperação de acesso.
- Asaas produção com credenciais reais e política comercial definida.
- Dashboard do tenant consumindo métricas SaaS.
