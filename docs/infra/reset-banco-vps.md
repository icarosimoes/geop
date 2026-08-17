# Reset e recriação do banco (VPS)

Procedimento operacional para zerar e popular novamente o banco PostgreSQL do
Registro/GEOP em produção (Docker Swarm na VPS `95.111.250.4`), e para resetar
a senha de um usuário diretamente no banco.

> ATENÇÃO: os comandos abaixo DESTROEM todos os dados do banco. Só usar em
> ambiente demo ou após confirmação explícita do usuário. Para produção com
> dados úteis, prefira backup (`docs/infra/teste-restore.md`).

## Identificadores fixos na VPS

| Item | Valor |
|---|---|
| Host VPS | `95.111.250.4` (SSH como `root`) |
| Service PostgreSQL | `registro_db` |
| Container DB (atual) | `registro_db.1.<id>` — obter com `docker ps` |
| Service API | `registro_api` |
| Container API (atual) | `registro_api.1.<id>` — obter com `docker ps` |
| Database | `registro` |
| Database user | `registro` |
| Senha do Postgres | lida do secret `registro_postgres_password` em `/run/secrets/registro_postgres_password` dentro do container DB |

Obter o container DB corrente:

```bash
ssh root@95.111.250.4 "docker ps --filter 'name=registro_db' --format '{{.Names}}'"
```

## 1. Recriar o banco do zero (DROP + CREATE + Alembic + seed)

Útil quando o schema divergiu, há lixo de seed antigo, ou se quer um ambiente
100% limpo como se a aplicação estivesse subindo pela primeira vez.

### 1.1 Encerrar conexões ativas

O `DROP DATABASE` falha se houver conexões abertas (a própria aplicação, o
backup, etc.). Encerre antes:

```bash
ssh root@95.111.250.4 "docker exec registro_db.1.<id> psql -U registro -d postgres \
  -c \"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = 'registro';\"
```

### 1.2 Drop e create

`dropdb`/`createdb` respeitam autocommit (não caem no erro de "transaction
block" do `psql -c DROP DATABASE`):

```bash
ssh root@95.111.250.4 "docker exec registro_db.1.<id> dropdb -U registro registro"
ssh root@95.111.250.4 "docker exec registro_db.1.<id> createdb -U registro -O registro registro"
```

> Nota: `psql -c "DROP DATABASE ..."` dentro do container falha com
> `DROP DATABASE cannot run inside a transaction block`. Use `dropdb`/`createdb`
> ou `DROP DATABASE` fora de transação (não há flag simples no `psql` do Alpine
> para isso — prefira `dropdb`).

### 1.3 Rodar migrations Alembic

```bash
ssh root@95.111.250.4 "docker exec registro_api.1.<id> alembic upgrade head"
```

Isso aplica todas as migrations (schema + seed de permissões e roles de hotel
das migrations `20260620_0018` e `20260621_0039`).

### 1.4 Rodar seed de demonstração

O `app/seed.py` recusa rodar em `ENVIRONMENT=production` sem senhas explícitas.
Passe-as via env:

```bash
ssh root@95.111.250.4 "docker exec \
  -e SEED_DEFAULT_PASSWORD=Demo@123 \
  -e PLATFORM_ADMIN_PASSWORD=AdminDemo@123 \
  registro_api.1.<id> python -m app.seed"
```

O seed cria:
- `companies` id=1 `Empresa Demonstração` (slug `empresa-demo`), id=2 `Filial Teste`
- `roles` admin por tenant (permissão `*`)
- `users` admin: id=1 `Ícaro Demonstração` / `icaro@registro.local`, id=2 `Ana Filial` / `ana@registro.local`
- `plans` (plano `professional`) e `subscriptions` (trial 14 dias)
- `PlatformUser` super_admin (`admin@registro.local`)

## 2. Personalizar a empresa demo (opcional)

Após o seed, ajuste a empresa id=1 e o usuário id=1 para dados fictícios de
demonstração (ex.: nome "Empresa Demo", seu e-mail real):

```bash
ssh root@95.111.250.4 "docker exec -i registro_db.1.<id> psql -U registro -d registro" <<'SQL'
UPDATE companies SET
  name = 'Empresa Demo',
  slug = 'empresa-demo',
  email = 'contato@empresademo.com.br',
  trade_name = 'Empresa Demo Ltda',
  document = '12.345.678/0001-90',
  address_street = 'Rua das Flores',
  address_number = '123',
  address_complement = 'Sala 101',
  address_neighborhood = 'Centro',
  address_city = 'São Paulo',
  address_state = 'SP',
  address_zip = '01000-000'
WHERE id = 1;

UPDATE users SET
  name = 'Icaro Simões',
  email = 'icarosimoes@jsmtecnologia.com.br',
  phone = '71999108868'
WHERE id = 1;
SQL
```

## 3. Reset de senha de um usuário (sem recriar o banco)

Para apenas trocar a senha de um usuário existente (ex.: esqueceu o acesso):

### 3.1 Gerar hash bcrypt no servidor

O container da API tem `bcrypt` instalado; use-o para gerar um hash válido:

```bash
ssh root@95.111.250.4 "docker exec registro_api.1.<id> python -c \
  \"import bcrypt; print(bcrypt.hashpw(b'NOVA_SENHA', bcrypt.gensalt()).decode())\""
```

> Nunca gerar hash manualmente no shell com `$` solto: o shell expande `$2b$...`
> e corrompe o hash. Use o `python -c` acima ou um script Python via `subprocess`.

### 3.2 Aplicar o hash

Use `psql -i` com heredoc para evitar expansão de shell no hash:

```bash
ssh root@95.111.250.4 "docker exec -i registro_db.1.<id> psql -U registro -d registro" <<'SQL'
UPDATE users SET password = '<HASH_GERADO>' WHERE email = 'USUARIO@EMAIL.com';
SQL
```

### 3.3 Verificar o login pela API

A API em produção fica em `api.geop.solidsd.com.br` (prefixo `/api/v1`). O
certificado Let's Encrypt é válido quando acessado direto no IP da VPS; o DNS
público aponta para Cloudflare, então para testar via curl use `--resolve`:

```bash
curl -s -X POST https://api.geop.solidsd.com.br/api/v1/auth/login \
  --resolve api.geop.solidsd.com.br:443:95.111.250.4 \
  -H 'Content-Type: application/json' \
  -d '{"email":"USUARIO@EMAIL.com","password":"NOVA_SENHA"}'
```

Resposta `200` com `access_token` confirma sucesso.

## 4. Armadilhas conhecidas

- **`DROP DATABASE` em transação** — use `dropdb`/`createdb`, não `psql -c`.
- **Empresa inativa bloqueia login** — a query de autenticação (`find_active_users_by_email`)
  filtra `Company.status == 'active'` e `Company.deleted_at IS NULL`. Se o
  login retorna `401 invalid_credentials` mesmo com senha correta, confira se a
  `companies` do usuário está ativa:
  ```sql
  SELECT id, name, status, deleted_at FROM companies WHERE id = <company_id>;
  ```
- **Hash corrompido por shell** — sempre aplicar password hash via `psql -i`
  com heredoc ou script Python, nunca com `psql -c "...$2b$..."` (o `$` some).
- **`plans` não é cascateada por `TRUNCATE companies`** — `plans` não referencia
  `companies`. Se fizer TRUNCATE parcial, limpe `plans` à parte antes de rodar o seed.
- **RLS (Row Level Security)** — a tabela `users` tem política `tenant_isolation`
  (`company_id = current_setting('app.current_company_id')`). Queries diretas no
  psql funcionam porque a setting não está setada (default permissivo no psql), mas
  código da aplicação precisa setar o `company_id` por request.

## 5. Consultas úteis

```sql
-- Listar empresas
SELECT id, name, slug, status, deleted_at FROM companies ORDER BY id;

-- Listar usuários
SELECT id, company_id, name, email, role_id, active FROM users ORDER BY id;

-- Resetar sequence de uma tabela
ALTER SEQUENCE companies_id_seq RESTART WITH 1;

-- TRUNCATE completo (cuidado: mata tudo em cascata)
TRUNCATE companies CASCADE;
-- + tabelas independentes, ex.:
TRUNCATE plans CASCADE;
```
