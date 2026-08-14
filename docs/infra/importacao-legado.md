# Importação de tenants via MySQL (V1)

O importador (`api/app/import_v1.py`) lê um dump MySQL do sistema legado (Chess Hotel / Aero) e carrega os dados no PostgreSQL do GEOP como um tenant isolado.

Cada hotel é um tenant separado identificado por um slug (ex: `aero-hotel`, `hotel-xyz`). O mesmo importador serve para qualquer cliente — basta passar o dump e o slug.

## Uso rápido

```bash
# Local (Docker Compose)
bash scripts/import-v1.sh <dump.sql> [slug-do-tenant]

# VPS (Docker Swarm)
bash scripts/import-v1-swarm.sh <dump.sql> [slug-do-tenant]
```

O slug default é `aero-hotel`. Exemplos:

```bash
# Aero Hotel (default)
bash scripts/import-v1-swarm.sh docs/aero-2026-06-19.sql

# Outro hotel
bash scripts/import-v1-swarm.sh dump-pousada-mar.sql pousada-mar

# Com nome personalizado
LEGACY_TENANT_NAME="Pousada Mar Azul" \
  bash scripts/import-v1-swarm.sh dump-pousada-mar.sql pousada-mar
```

## Como funciona o script Swarm

O script `import-v1-swarm.sh` roda da máquina local e opera na VPS via SSH:

1. **Copia o dump** para `/tmp` na VPS via SCP
2. **Sobe MySQL temporário** numa rede bridge isolada (`registro-v1-import`)
3. **Carrega o dump** no MySQL
4. **Conecta o PostgreSQL** do stack à rede bridge
5. **Roda migrations** (`alembic upgrade head`) num container efêmero da API
6. **Executa o importador** (`python -m app.import_v1`) no mesmo container
7. **Limpa tudo** — remove MySQL, rede bridge e dump remoto

### Por que container efêmero?

No Swarm com múltiplos nós, os containers da API podem estar em nós diferentes do manager. O script cria um container efêmero no manager (onde o PostgreSQL está) usando a mesma imagem da API em produção. Isso evita problemas de rede cross-node.

### asyncmy

A imagem da API em produção pode não ter o driver MySQL (`asyncmy`). O script instala via `pip install` dentro do container efêmero antes de rodar o importador. O container é descartado ao final — a imagem original não é afetada.

## Variáveis de ambiente

### Argumentos do script

| Argumento | Posição | Default | Descrição |
| --- | --- | --- | --- |
| `dump.sql` | 1 (obrigatório) | — | Caminho local do dump MySQL |
| `slug` | 2 (opcional) | `aero-hotel` | Slug do tenant no GEOP |

### Variáveis configuráveis

| Variável | Default | Descrição |
| --- | --- | --- |
| `VPS_HOST` | `95.111.250.4` | IP da VPS |
| `VPS_USER` | `root` | Usuário SSH |
| `STACK_NAME` | `registro` | Nome do stack no Swarm |
| `MYSQL_PASSWORD` | `import-v1-temp` | Senha do MySQL temporário |
| `LEGACY_TENANT_NAME` | derivado do slug | Nome de exibição do tenant (ex: `Pousada Mar Azul`) |
| `LEGACY_TENANT_EMAIL` | `legado@registro.local` | E-mail do tenant |
| `LEGACY_DEMO_PASSWORD` | (vazio) | Se definido, cria usuário `v1-demo@registro.local` |

### Derivação automática do nome

Se `LEGACY_TENANT_NAME` não for informado, o nome é derivado do slug:
- `aero-hotel` → `Aero Hotel`
- `pousada-mar` → `Pousada Mar`

Para nomes com acentos ou formatação específica, passe explicitamente.

## O que é importado

| Conjunto | Tabela destino | Observação |
| --- | --- | --- |
| Usuários | `users` | Hashes bcrypt Laravel preservados |
| Setores | `sectors` | |
| Locais | `locations` | |
| Funções | `functions` | |
| Procedimentos | `procedures` | Inclui `procedure_files` |
| Ocorrências | `occurrences` | + comentários e participantes |
| Reuniões | `meetings` | + `meeting_participants` + `meeting_subjects` |
| Relatórios de turno | `shift_reports` | Sub-tabelas em payload JSON |
| Check suites | `module_records` (module=inspecoes) | Items em payload JSON |
| Auditorias | `module_records` (module=manutencao) | Items em payload JSON |
| Notificações | `notifications` | Categoria `legacy` |

### O que NÃO é importado

- **Anexos/arquivos físicos** — uploads do Laravel ficam no filesystem do servidor antigo. Requerem migração separada ao MinIO.
- **Configurações do sistema** — cada tenant começa com configurações padrão do GEOP.

## Permissões e roles

O importador cria dois roles para cada tenant:

- **admin** — permissão wildcard `*`, acesso total. Todos os usuários importados recebem este role.
- **legacy-admin** — preserva as ACLs originais do Laravel (códigos como `legacy.occurrencescontroller.index`). Mantido apenas para referência, não é usado no controle de acesso.

Após a importação, roles adicionais (gerente, recepção, governança, etc.) podem ser criados pela interface de Perfis do GEOP.

## Idempotência e reimportação

- O ETL é idempotente por `(company_id, legacy_id)` — registros existentes são atualizados, novos são inseridos.
- O checksum SHA-256 do dump é registrado em `legacy_import_runs`. Se o mesmo checksum já foi processado, o importador pula a execução.
- Para reimportar com dump atualizado (dados mais recentes), rode o script com o novo arquivo — o checksum diferente dispara nova execução.
- É seguro rodar múltiplas vezes. Não duplica dados.

## Login após importação

- Usuários da V1 logam com **e-mail e senha do sistema antigo** (hashes bcrypt preservados).
- Se o mesmo e-mail existir em mais de um tenant, o login solicita escolha da empresa.
- Se `LEGACY_DEMO_PASSWORD` foi informado, existe o usuário `v1-demo@registro.local` para testes.

## Validação pós-importação

```bash
# Na VPS, via container do DB
DB=$(docker ps -q -f "name=registro_db" | head -1)

# Contagens por tenant
docker exec "$DB" psql -U registro -c "
  SELECT c.slug,
    (SELECT count(*) FROM users WHERE company_id = c.id AND deleted_at IS NULL) as users,
    (SELECT count(*) FROM occurrences WHERE company_id = c.id AND deleted_at IS NULL) as occurrences,
    (SELECT count(*) FROM meetings WHERE company_id = c.id AND deleted_at IS NULL) as meetings,
    (SELECT count(*) FROM shift_reports WHERE company_id = c.id) as shift_reports
  FROM companies c ORDER BY c.id;
"

# Verificar roles e permissões de um tenant específico
docker exec "$DB" psql -U registro -c "
  SELECT r.code, r.name, string_agg(p.code, ', ') as permissions
  FROM roles r
  JOIN role_permissions rp ON rp.role_id = r.id
  JOIN permissions p ON p.id = rp.permission_id
  WHERE r.company_id = (SELECT id FROM companies WHERE slug = 'aero-hotel')
  GROUP BY r.id ORDER BY r.code;
"

# Histórico de importações
docker exec "$DB" psql -U registro -c "
  SELECT source, status, started_at, finished_at,
    left(checksum_sha256, 12) as checksum, report
  FROM legacy_import_runs ORDER BY started_at DESC;
"
```

## Procedimento para novo cliente

1. Receber o dump MySQL do cliente (`.sql`).
2. Escolher um slug (ex: `hotel-centro`, `pousada-praia`). Usar apenas letras minúsculas, números e hífens.
3. Rodar o importador:
   ```bash
   LEGACY_TENANT_NAME="Hotel Centro SP" \
     bash scripts/import-v1-swarm.sh dump-hotel-centro.sql hotel-centro
   ```
4. Validar contagens (queries acima).
5. Testar login com um usuário real do dump.
6. Informar o cliente que pode acessar com e-mail e senha do sistema antigo.

## Regras de segurança

- O dump nunca é versionado nem incluído em imagem Docker.
- O MySQL temporário é efêmero — só existe durante a importação, é destruído no final.
- Senhas Laravel bcrypt são preservadas. Rehash só ocorre se decidido explicitamente.
- O dump é removido da VPS ao final do script.
