# Observabilidade local (GlitchTip)

Rastreamento de erros da API, do banco (exceções do SQLAlchemy) e do frontend (web),
usando [GlitchTip](https://glitchtip.com/) — compatível com o SDK do Sentry, mas
open-source e self-hosted.

**Escopo: apenas desenvolvimento local.** Não existe stack de observabilidade na VPS
de produção (`docker-stack.yml`); nada aqui é aplicado em produção.

## Subir o GlitchTip

Os serviços ficam atrás do profile `observability` para não subir por padrão:

```bash
docker compose --profile observability up -d
```

Isso sobe `glitchtip-postgres`, `glitchtip-redis`, `glitchtip-migrate` (roda as
migrations e sai), `glitchtip-web` (porta `8080`) e `glitchtip-worker` (processa
eventos em background via Celery).

## Configuração inicial (uma vez)

1. Acesse `http://localhost:8080` e clique em "Registrar" (registro aberto habilitado
   só neste ambiente local via `ENABLE_OPEN_USER_REGISTRATION=true`).
2. Não há servidor de e-mail real — os e-mails de verificação vão para o log do
   container: `docker logs geop-glitchtip-web-1 --tail 50` (procure pelo link de
   confirmação).
3. Crie uma organização e, dentro dela, dois projetos: um para a API (plataforma
   `Python`/`FastAPI`) e um para o web (plataforma `Next.js`).
4. Cada projeto expõe um DSN em Configurações → "Client Keys (DSN)".

## Ligar a API e o web ao GlitchTip

No `.env` da raiz do repo (nunca commitado). Note que o host muda conforme quem faz a
chamada: código rodando **dentro dos containers** (API e o lado servidor do Next.js)
não enxerga `localhost:8080` — precisa de `host.docker.internal`, que só resolve porque
os serviços `api` e `web` declaram `extra_hosts: host.docker.internal:host-gateway`.
Já o SDK client-side (browser, rodando no host) precisa de `localhost:8080`:

```env
SENTRY_DSN_API=http://<chave>@host.docker.internal:8080/<id-do-projeto-api>
SENTRY_DSN_WEB_INTERNAL=http://<chave>@host.docker.internal:8080/<id-do-projeto-web>
SENTRY_DSN_WEB_PUBLIC=http://<chave>@localhost:8080/<id-do-projeto-web>
```

Reinicie os serviços para aplicar:

```bash
docker compose up -d api web
```

Se as variáveis ficarem vazias, o SDK simplesmente não inicializa — não há custo nem
chamadas de rede.

## Onde cada SDK está plugado

- **API**: `api/app/main.py` — `sentry_sdk.init()` roda apenas se `settings.sentry_dsn`
  estiver preenchido. Captura exceções não tratadas de qualquer endpoint, incluindo
  erros do SQLAlchemy/asyncpg (timeout, violação de constraint, etc.).
- **Web**: `web/instrumentation.ts` (hook de servidor/edge) e
  `web/instrumentation-client.ts` (hook de browser), inicializando a partir de
  `web/sentry.server.config.ts` e `web/sentry.edge.config.ts`. Captura exceções não
  tratadas em Server Actions, Route Handlers e no client.

Não há upload de source maps nem tunnel route configurados — desnecessário para
debug local, onde o código já roda sem minificação.

## Parar

```bash
docker compose --profile observability down
```

Use `-v` junto se quiser apagar o histórico de erros armazenado (`registro-glitchtip-postgres-data`).

## Validado

Setup testado ponta a ponta em 2026-07-10: `sentry_sdk.capture_message` na API e
`Sentry.captureMessage` no web chegaram como eventos nos respectivos projetos
(`registro-api`, `registro-web`) dentro do GlitchTip. Organização `registro`, projetos
`registro-api` (id 1) e `registro-web` (id 2) e usuário `admin@registro.local` já
existem neste ambiente local (senha combinada fora deste documento).
