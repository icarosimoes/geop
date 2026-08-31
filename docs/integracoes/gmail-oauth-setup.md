# OAuth2 do Google (Gmail) — email_client

## Por que existe

O Gmail bloqueia login IMAP com a senha normal da conta desde 2022 (sem exceção
pra contas pessoais `@gmail.com`). Contas de e-mail Gmail no email_client
(`/email` → Contas → aba Gmail → "Conectar com Google") autenticam via OAuth2 +
XOAUTH2 em vez de usuário+senha — a única forma que o Google ainda aceita pra
acesso IMAP de terceiros.

Sem as variáveis abaixo configuradas, `POST /email-client/oauth/start` responde
`400 {"code": "oauth_not_configured"}` e a aba Gmail fica indisponível; contas
Microsoft/IMAP/POP3 por senha continuam funcionando normalmente.

## Passo a passo (Google Cloud Console)

1. Crie (ou reutilize) um projeto em [console.cloud.google.com](https://console.cloud.google.com/).
2. **APIs e serviços → Biblioteca** → ative a **Gmail API** (o scope de IMAP
   `https://mail.google.com/` depende dela estar ativada no projeto).
3. **APIs e serviços → Tela de consentimento OAuth**:
   - Tipo de usuário: **Externo**.
   - Nome do app, e-mail de suporte: qualquer um do time.
   - Escopos: adicione `https://mail.google.com/` (aparece como escopo
     "restrito" — o Google vai avisar que requer verificação para uso amplo,
     ver limitação abaixo).
   - **Usuários de teste**: adicione aqui o e-mail de **cada conta Gmail** que
     for conectada ao GEOP (ex.: `redacaog7bahia@gmail.com`). Enquanto o app
     estiver em modo **Testing**, só esses e-mails conseguem autorizar.
   - Publique como **Testing** (não "Em produção" — evita o processo de
     verificação do Google por enquanto).
4. **APIs e serviços → Credenciais → Criar credenciais → ID do cliente OAuth**:
   - Tipo de aplicativo: **Aplicativo da Web**.
   - **URIs de redirecionamento autorizados**: precisa ser **exatamente** a
     mesma URL configurada em `GOOGLE_OAUTH_REDIRECT_URI` (abaixo) — qualquer
     diferença (barra final, http vs https, porta) faz o Google rejeitar o
     callback com `redirect_uri_mismatch`.
     - Dev: `http://localhost:8000/api/v1/email-client/oauth/callback`
     - Produção: `https://<host-da-api>/api/v1/email-client/oauth/callback`
5. Copie o **Client ID** e o **Client secret** gerados.

## Variáveis de ambiente

```bash
GOOGLE_OAUTH_CLIENT_ID=<client id do passo 5>
GOOGLE_OAUTH_CLIENT_SECRET=<client secret do passo 5>
GOOGLE_OAUTH_REDIRECT_URI=http://localhost:8000/api/v1/email-client/oauth/callback  # ou a URL de produção
```

Em dev, coloque no `.env` da raiz (ver `.env.example`) e reinicie o container
`api` (`docker compose up -d api` já pega as novas env vars). Em produção, siga
o mesmo mecanismo de secrets já usado para `JWT_SECRET`/`BREVO_API_KEY` no
Swarm — `GOOGLE_OAUTH_CLIENT_SECRET_FILE` também é aceito (mesmo padrão
`_file` dos outros segredos em `core/config.py`), se preferir montar como
Docker secret em vez de env var.

## Limitação conhecida: modo Testing

Com a tela de consentimento em **Testing**, só os e-mails cadastrados como
"usuários de teste" (até 100) conseguem autorizar — qualquer outro Gmail vê uma
tela de bloqueio do Google. Isso é suficiente para o uso atual (poucas contas
por tenant), mas **não escala** para "qualquer cliente do GEOP conecta o
próprio Gmail livremente": isso exigiria publicar o app e passar pela
verificação do Google para o scope restrito `https://mail.google.com/`
(processo do próprio Google, pode levar dias/semanas, exige política de
privacidade pública e justificativa do uso do scope). Não é necessário agora —
só documentado como próximo passo caso o uso cresça.

## Reconectar uma conta quebrada

Se uma conta Gmail cadastrada por senha parar de autenticar
(`AUTHENTICATIONFAILED`), **não precisa excluir a conta antes**: adicionar uma
conta Gmail de novo com "Conectar com Google" e autorizar com o mesmo e-mail
atualiza a conta existente para OAuth em vez de criar uma duplicata (ver
`upsert_oauth_account` em `api/app/domain/email_client/service.py`).
