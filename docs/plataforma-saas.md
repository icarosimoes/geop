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
- **Usuários**: CRUD da equipe interna da plataforma (`PlatformUser`), com papéis `super_admin`/`support`/`billing`/`read_only`.
- **Suporte**: fila de pedidos abertos pelo botão de Ajuda do tenant (`web/`), com filtro por status (pendente/contatado/resolvido).
- **Uso**: consumo por tenant (usuários ativos, ocorrências do mês), agregado por métrica; snapshot gerado sob demanda (sem Celery no Registro).
- **Configurações**: e-mail transacional (Brevo) usado pela API para convites e avisos do sistema, no mesmo padrão do Aloji — sobrepõe as variáveis de ambiente, sem precisar de redeploy.
- **Auditoria**: tabela de logs administrativos da plataforma (`platform_audit_logs`).
- **Auth**: Server Actions + httpOnly cookies.
- **API proxy**: route handler `/api/proxy/[...path]` para mutations client-side proxeadas para `/platform/*`.

Ver `docs/api-reference.md` (seções "Plataforma — usuários, suporte e uso" e "Plataforma — e-mail transacional") para o contrato completo dos endpoints.

### Design system (revisão 2026-07-12)

Revisão de UI/UX ponta a ponta do painel (código + inspeção visual de todas as telas), com correções aplicadas:

- **Sempre tema claro**: removido o `@media (prefers-color-scheme: dark)` de `globals.css` — o painel não deve escurecer automaticamente conforme a preferência do SO/navegador (decisão do usuário, não é bug de contraste isolado).
- **Marca unificada**: `--color-brand`/`--ring` agora usam o navy/teal reais da marca (`#1D3461`/`#2BC4B4`), os mesmos da sidebar e do login, em vez do azul genérico que vinha do template.
- **Um único menu de usuário**: o avatar duplicado no cabeçalho (`TopUserMenu`) foi removido; só existe o menu no rodapé da sidebar.
- **Confirmações e erros consistentes**: `confirm()`/`alert()` nativos do browser foram substituídos por `ConfirmDialog` (`components/ui/confirm-dialog.tsx`, sobre o `Dialog` Radix) e por toasts (`sonner`) nas ações de Empresas e Usuários.
- **Modais e dropdowns no Radix**: os modais de Empresas/Usuários e os menus (usuário da sidebar, ações de assinatura) passaram a usar os componentes `Dialog`/`DropdownMenu` já existentes em `components/ui/`, em vez de implementações manuais sem focus trap nem fechamento por Esc.

Pendências dessa revisão (componentização de filtros, paginação de Auditoria, CRUD de Planos, dashboard mais rico) estão registradas em `backlog.md` (P12).

### Brevo por tenant: teste de envio (2026-07-13)

A configuração de Brevo por tenant (`/configuracoes` → Integrações no `web/`) já existia; ganhou um botão "Testar envio" (`POST /settings/brevo/test`) que dispara um e-mail real com a config salva, no mesmo padrão que a Evolution API já tinha para WhatsApp. Ver `docs/api-reference.md` (seção "Testar envio (Brevo por tenant)") e `backlog.md` (P13) para o contrato e as pendências.

### Brevo por tenant: fallback para a config da plataforma (2026-07-13)

Quando o tenant **não** configurou Brevo próprio (`company_settings.brevo` sem `api_key`), o envio de notificações por e-mail (`app.integrations.notifications.prepare_notifications`) agora cai para a config global do painel admin (`platform_settings.email`, a mesma resolvida por `get_effective_email_config` — que por sua vez cai para as env vars `BREVO_API_KEY`/`MAIL_FROM_ADDRESS`/`MAIL_FROM_NAME` se nem o painel tiver sido configurado). Prioridade: **tenant > painel admin > env vars**. `from_address`/`from_name` seguem a mesma cascata campo a campo (se o tenant configurou só o remetente mas não a API key, o remetente do tenant é preservado e só a API key vem do nível acima). Antes desta mudança, um tenant sem Brevo próprio simplesmente não recebia nenhum e-mail de notificação de módulo (ocorrências, solicitações fiscais etc.) — só o convite de usuário (`POST /users/invite`) já usava esse fallback.

### Impersonar tenant a partir do admin (2026-07-14)

Botão "Entrar como" na tela Empresas (`admin/app/(app)/tenants/tenants-client.tsx`, ícone `LogIn`) permite ao operador de plataforma acessar o app do tenant (`web/`) sem senha, para suporte — mesmo padrão do Aloji.

Como `admin` (porta 3001) e `web` (porta 3000) são origins diferentes, sem cookie compartilhado, o fluxo usa um ticket de curta duração:

1. `POST /platform/tenants/{id}/impersonate` (autenticado como `PlatformUser`) escolhe o primeiro usuário ativo do tenant (`User.active=True, deleted_at IS NULL, ORDER BY id`), gera um JWT `type=impersonation` de 2 minutos e devolve `{web_url: "{REGISTRO_WEB_URL}/impersonate?ticket=..."}`. Registra `PlatformAuditLog` (`action="tenant.impersonate"`, `target_type="company"`, payload com `user_id`/`user_email`). 404 (`tenant_has_no_users`) se o tenant não tiver usuário ativo.
2. O admin abre `web_url` em nova aba.
3. `web/app/impersonate/route.ts` (route handler público, excluído do `matcher` de `middleware.ts` — não vai para `PUBLIC_PATHS` para não colidir com a regra de "já autenticado → dashboard") troca o ticket por uma sessão real via `POST /auth/impersonate`, seta os cookies `tenant_token`/`tenant_refresh_token` (`setTokenCookies`) e redireciona para `/dashboard`. Ticket inválido/expirado → `/login?error=impersonation`.

Não existe hoje um flag "owner"/"admin garantido" no model `User`; "primeiro usuário ativo" é um proxy razoável mas pode não ser sempre o dono da conta. `web/middleware.ts` não é bind-mounted no Compose (só `web/app`, `web/components`, `web/lib`) — mudanças nele exigem `docker compose build web`, não só restart.

## Comercial e cobrança (implementado)

- CRUD auditado de tenants, planos e assinaturas — endpoints platform com POST/GET/PATCH/DELETE, todos auditados via `PlatformAuditLog`.
- Lifecycle: trial 14 dias → past_due (expiração) → suspended (7 dias de tolerância, bloqueia login) → reativação via endpoint admin.
- Asaas sandbox: `AsaasClient` async com httpx, webhook autenticado e idempotente (dedup via `webhook_events`), reconciliação periódica (`POST /platform/billing/reconcile`).

## Próximas capacidades

- Convite e recuperação de acesso.
- Asaas produção com credenciais reais e política comercial definida.
- Dashboard do tenant consumindo métricas SaaS.
