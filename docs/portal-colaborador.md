# Portal do Colaborador (ponto, escala e contracheque)

PWA separado (`colaborador/`) para o `Employee` (cadastro de RH — ver
[cadastro-funcionarios.md](cadastro-funcionarios.md)) bater ponto pelo celular com
validação de geolocalização, consultar sua escala e baixar seu contracheque. Não usa
conta de login (`User`) nem o menu completo do Registro — é um app instalável dedicado,
paralelo a `web/` e `admin/` na raiz do monorepo.

Complementa a integração de ponto físico já existente (relógio Control iD via webhook,
ver [integracao-escala-ponto.md](integracao-escala-ponto.md)) e o catálogo de
equipamentos ([relogios-de-ponto-catalogo.md](relogios-de-ponto-catalogo.md)) e o agente
Go de ponte local (`agent/`) para o mesmo relógio físico. As três formas de bater ponto —
relógio físico, agente Go, app mobile — convergem no mesmo `TimePunch` e na mesma lógica
de status (`resolve_schedule_for_date`/`evaluate_status`), diferenciadas pelo campo
`source` (`device`, `manual`, `mobile`).

## Por que um namespace de autenticação separado

`Employee` é puramente cadastro de RH e nunca teve credencial própria — só `User` loga na
API (ver `user_id` opcional em `Employee`, "nem todo employee loga no sistema"). Criar uma
sessão para o próprio funcionário exigiu um mecanismo de auth **completamente isolado** do
login de `User`, para que nenhum dos dois tokens abra as rotas do outro:

- Token `employee_session` (`api/app/core/security.py`): claims mínimos (`sub`=employee_id,
  `company_id`, `type`), **sem** `permissions` nem `role_id` — impossível de escalar para
  rotas administrativas mesmo que vazado.
- Dependency `require_employee_session` (`api/app/domain/timeclock/mobile_auth.py`): só
  aceita `type == "employee_session"`, nunca `access` (User). `OAuth2PasswordBearer` próprio
  apontando para `/api/v1/timeclock/mobile/login`, separado do `oauth2_scheme` de `auth/router.py`.
- Testado explicitamente nos dois sentidos (`api/tests/test_timeclock_mobile.py`): um
  `employee_session` token não abre nenhuma rota protegida por `require_permission`, e um
  `access` token de `User` não abre `POST /timeclock/mobile/punch`.
- TTL curto (60 min), sem refresh — o uso é pontual (bater ponto, checar escala/contracheque),
  não uma sessão de trabalho longa. Expirado, o app redireciona para o login.

## Autenticação por PIN

Login por `company_slug` + `registration_number` (matrícula, já existente em `Employee`) +
PIN numérico curto — não senha completa, decisão validada com o usuário porque o uso é em
celular pessoal ou compartilhado no balcão, com necessidade de digitação rápida.

Credenciais isoladas em tabela dedicada `employee_credentials` (mesmo padrão de tabela
separada por preocupação já usado por `TimeClockEnrollment`), nunca dentro de `Employee`:

- `pin_hash` (bcrypt) — PIN nunca fica em texto puro.
- `failed_attempts`/`locked_until` — bloqueio temporário após tentativas malsucedidas
  (`PIN_MAX_ATTEMPTS = 5`, `PIN_LOCKOUT_MINUTES = 15` em `timeclock/service.py`). Um PIN
  curto é fraco por natureza; lockout + TTL curto do token são a mitigação consciente, não
  uma senha forte.
- `must_change_pin` — força troca do PIN default assim que o admin reseta.

Fluxo de gestão de PIN:

- `POST /timeclock/employees/{employee_id}/pin/reset` (admin, `timeclock.manage`) — gera
  PIN novo, marca `must_change_pin=True`, gera `AuditEvent`.
- `POST /timeclock/mobile/pin` (funcionário autenticado) — troca o próprio PIN.

## Geofencing

`Location` (ver [domain-model.md](domain-model.md)) ganhou `latitude`, `longitude` e
`geofence_radius_m` (default 100m). `Employee` ganhou `location_id` (não existia vínculo
direto antes — a cadeia `Employee → Sector → Location` não existe no schema, então o campo
foi adicionado diretamente em `Employee`).

`POST /timeclock/mobile/punch` recebe `latitude`/`longitude` do navegador
(`navigator.geolocation`), calcula a distância até a `Location` do funcionário via
Haversine (`haversine_distance_m` em `timeclock/service.py`, testado com coordenadas
conhecidas) e:

- `distance_m > geofence_radius_m` → rejeita com `422 OUT_OF_RANGE` e a distância calculada,
  para o app mostrar "você está a Xm do estabelecimento".
- `Location` do funcionário não configurada (sem `location_id` ou sem lat/lng) → rejeita com
  `422 LOCATION_NOT_CONFIGURED` em vez de aceitar sem geofencing silenciosamente.
- Dentro do raio → cria `TimePunch` com `source="mobile"`, `created_by_user_id=None`,
  lat/lng/`distance_m` preenchidos, reaproveitando a mesma `resolve_schedule_for_date`/
  `evaluate_status` do webhook do relógio físico para computar `status` de forma consistente.

## Escala e contracheque

- `GET /timeclock/mobile/schedule?start&end` reaproveita `get_calendar()` (mesma função
  usada pela tela `/ponto` do `web/`), filtrado pelo `employee_id` do próprio token — um
  funcionário nunca vê a escala de outro.
- Contracheque: tabela dedicada `employee_payslips` (`employee_id`, `reference_month`,
  `attachment_id`) associa um PDF por competência. O upload em si reaproveita o fluxo
  genérico de `attachments` (`api/app/domain/attachments/`), que ganhou `"employee_payslip"`
  em `ALLOWED_ENTITY_TYPES` — nenhuma lógica de upload/validação de arquivo foi duplicada.
- `GET /timeclock/mobile/payslips/{id}/download` sempre valida que o `payslip_id` pertence
  ao `employee_id` do token antes de servir o arquivo (`StreamingResponse` via
  `app/core/storage.py`) — nunca confia em IDs recebidos do client. Testado explicitamente
  (funcionário A não baixa contracheque de funcionário B da mesma empresa).

## Endpoints (`api/app/domain/timeclock/mobile_router.py`, prefixo `/timeclock/mobile`)

| Rota | Auth | Descrição |
| --- | --- | --- |
| `POST /login` | nenhuma (rate limit 10/min) | `company_slug` + `registration_number` + `pin` → `employee_session` token |
| `POST /pin` | employee_session | troca o próprio PIN |
| `POST /punch` | employee_session (rate limit 30/min) | lat/lng → cria `TimePunch` com geofencing |
| `GET /status` | employee_session | próximo tipo de batida esperado (in/out) |
| `GET /schedule` | employee_session | escala do próprio funcionário (`CalendarEntry[]`) |
| `GET /payslips` | employee_session | lista os próprios contracheques |
| `GET /payslips/{id}/download` | employee_session | download do PDF, valida posse |

Endpoint administrativo (no router principal `timeclock/router.py`, `timeclock.manage`):
`POST /timeclock/employees/{employee_id}/pin/reset` e upload de contracheque (RH,
`entity_type="employee_payslip"` em `attachments` + registro em `EmployeePayslip`).

## Frontend (`colaborador/`)

App Next.js 16 App Router independente (porta 3002 em dev, serviço `colaborador` no
`docker-compose.yml`), sem menu completo do Registro:

- `login/page.tsx` — company_slug + matrícula + PIN; `login/trocar-pin/page.tsx` quando
  `must_change_pin` vem `true` na resposta de login.
- `ponto/page.tsx` — botão único, `navigator.geolocation.getCurrentPosition`, estados
  visuais de localizando/enviando/sucesso/erro (com tratamento explícito de permissão de
  localização negada e de `OUT_OF_RANGE`/`LOCATION_NOT_CONFIGURED`).
- `escala/page.tsx` — próximos 14 dias via `GET /timeclock/mobile/schedule`.
- `contracheque/page.tsx` — lista + download; o download é servido por um route handler
  próprio (`app/api/payslips/[id]/route.ts`) que injeta o `Authorization: Bearer` no
  servidor e faz proxy do stream do backend, porque um `<a href>` normal não carrega
  header de autenticação.
- Sessão: token `employee_session` em cookie httpOnly `employee_token` (sem refresh — 401
  limpa o cookie e redireciona para `/login`), gate central em `middleware.ts`.
- `next.config.ts` própio: diferente de `web/next.config.ts` (que bloqueia geolocalização
  via `Permissions-Policy: geolocation=()`), aqui a policy permite `geolocation=(self)`,
  já que é a funcionalidade central do app.
- PWA: `public/manifest.json` e `public/sw.js` próprios — o service worker cacheia só o
  shell estático, nunca respostas de API (ponto/escala/contracheque não podem ficar stale).

## Migrations

`api/alembic/versions/20260704_0047_employee_portal.py`: `Location` (lat/lng/raio),
`Employee.location_id`, tabela `employee_credentials`, `TimePunch` (lat/lng/distance_m),
tabela `employee_payslips` — todas com policies RLS por `company_id`, aplicadas e
verificadas contra o Postgres do Docker Compose.

## Testes

`api/tests/test_timeclock_mobile.py` (14 testes): Haversine, login (sucesso/PIN
errado/slug errado/lockout), isolamento de namespace de token nos dois sentidos, punch
dentro/fora do raio, location não configurada, isolamento de escala e contracheque entre
funcionários, fluxo completo de reset de PIN pelo admin + troca pelo funcionário.

## Limitações conhecidas

- Contexto seguro (HTTPS) é exigido pelo browser para `navigator.geolocation` fora de
  `localhost` — em produção o PWA precisa estar servido em HTTPS, o que já é o padrão do
  deploy Swarm do Registro.
- PIN numérico curto é uma escolha consciente de UX sobre segurança forte — mitigado por
  lockout e TTL curto do token, não substitui autenticação forte se o caso de uso mudar
  (ex: se o app passar a expor dados mais sensíveis que ponto/escala/contracheque).
- Upload de contracheque é manual pelo RH (um PDF por competência); não há integração
  automática com folha de pagamento/ERP nesta primeira versão.
