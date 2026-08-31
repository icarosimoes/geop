# Teste de Restore — Runbook

## Objetivo

Validar que o procedimento de restore do GEOP funciona **end-to-end**: desde a leitura do dump PostgreSQL e do espelho MinIO ate a verificacao de integridade dos dados e acesso via API. Este teste garante que, em caso de desastre real, a equipe consiga restaurar o sistema dentro do RTO de 1 hora.

## Frequencia

**Mensal**, preferencialmente no **primeiro domingo do mes**, em horario de baixa utilizacao (antes das 8h ou apos as 22h).

## Pre-requisitos

- [ ] Acesso SSH ao servidor de producao (node manager do Swarm)
- [ ] Docker funcionando e services do GEOP ativos
- [ ] Pelo menos 1 backup recente disponivel em `/backups/`
- [ ] `mc` (MinIO Client) instalado ou acessivel no host
- [ ] Espaco em disco suficiente para subir um container PostgreSQL temporario (~2x o tamanho do dump)

---

## Procedimento passo a passo

### 1. Verificar backups disponiveis

```bash
# Listar dumps do PostgreSQL
ls -lah /var/lib/docker/volumes/registro_registro-backups/_data/*.dump

# Verificar checksums
cd /var/lib/docker/volumes/registro_registro-backups/_data/
for f in *.dump; do
  echo "--- $f ---"
  sha256sum -c "${f}.sha256" 2>/dev/null && echo "OK" || echo "CHECKSUM FALHOU"
done

# Listar backup MinIO
ls -lah /var/lib/docker/volumes/registro_registro-backups/_data/minio/registro-attachments/
```

**Anotar**: nome do dump escolhido para teste, tamanho, data de criacao.

### 2. Criar ambiente de teste isolado

Subir um container PostgreSQL temporario que **nao** interfere no banco de producao:

```bash
# Criar rede isolada para o teste
docker network create restore-test-net

# Subir PostgreSQL de teste
docker run -d \
  --name restore-test-db \
  --network restore-test-net \
  -e POSTGRES_USER=registro \
  -e POSTGRES_PASSWORD=teste-restore-temp \
  -e POSTGRES_DB=registro \
  postgres:17-alpine

# Aguardar o banco estar pronto
sleep 5
docker exec restore-test-db pg_isready -U registro
```

### 3. Restaurar o dump no container de teste

```bash
DUMP_FILE="/var/lib/docker/volumes/registro_registro-backups/_data/registro_YYYYMMDD_HHMMSS.dump"

# Copiar dump para o container de teste
docker cp "$DUMP_FILE" restore-test-db:/tmp/restore.dump

# Validar integridade do dump
docker exec restore-test-db pg_restore --list /tmp/restore.dump > /dev/null 2>&1
echo "Validacao: $?"  # 0 = OK

# Restaurar
docker exec -e PGPASSWORD=teste-restore-temp restore-test-db \
  pg_restore -U registro -d registro --clean --if-exists /tmp/restore.dump

echo "Restore finalizado: $?"
```

### 4. Validar integridade dos dados

#### 4.1 Contagem de registros nas tabelas principais

```bash
docker exec -e PGPASSWORD=teste-restore-temp restore-test-db psql -U registro -d registro -c "
SELECT 'companies' AS tabela, COUNT(*) AS total FROM companies
UNION ALL
SELECT 'users', COUNT(*) FROM users WHERE deleted_at IS NULL
UNION ALL
SELECT 'work_orders', COUNT(*) FROM work_orders WHERE deleted_at IS NULL
UNION ALL
SELECT 'registries', COUNT(*) FROM registries WHERE deleted_at IS NULL
UNION ALL
SELECT 'audit_events', COUNT(*) FROM audit_events
UNION ALL
SELECT 'alembic_version', COUNT(*) FROM alembic_version
ORDER BY tabela;
"
```

**Anotar** as contagens. Comparar com os valores do mes anterior (se disponivel).

#### 4.2 Verificar constraints e integridade referencial

```bash
# Verificar que nao ha constraints violadas
docker exec -e PGPASSWORD=teste-restore-temp restore-test-db psql -U registro -d registro -c "
SELECT conname, conrelid::regclass AS tabela, contype
FROM pg_constraint
WHERE contype IN ('f', 'c', 'u')
ORDER BY conrelid::regclass, contype;
"

# Verificar versao da migration (alembic)
docker exec -e PGPASSWORD=teste-restore-temp restore-test-db psql -U registro -d registro -c "
SELECT version_num FROM alembic_version;
"
```

#### 4.3 Testar que dados de autenticacao estao intactos

```bash
# Verificar que usuarios admin existem e tem password_hash
docker exec -e PGPASSWORD=teste-restore-temp restore-test-db psql -U registro -d registro -c "
SELECT id, email, full_name, is_active,
       CASE WHEN password_hash IS NOT NULL THEN 'SIM' ELSE 'NAO' END AS tem_senha
FROM users
WHERE deleted_at IS NULL AND role = 'admin'
LIMIT 5;
"
```

#### 4.4 Verificar isolamento por tenant (company_id)

```bash
# Garantir que nao existem registros orfaos (sem company)
docker exec -e PGPASSWORD=teste-restore-temp restore-test-db psql -U registro -d registro -c "
SELECT 'users sem company' AS verificacao, COUNT(*) AS total
FROM users WHERE company_id IS NULL AND deleted_at IS NULL
UNION ALL
SELECT 'work_orders sem company', COUNT(*)
FROM work_orders WHERE company_id IS NULL AND deleted_at IS NULL;
"
```

### 5. Validar backup do MinIO

```bash
MINIO_BACKUP="/var/lib/docker/volumes/registro_registro-backups/_data/minio/registro-attachments"

# Contar arquivos no backup
echo "Arquivos no backup MinIO:"
find "$MINIO_BACKUP" -type f | wc -l

# Verificar tamanho total
du -sh "$MINIO_BACKUP"

# Comparar com o bucket ativo (se mc estiver disponivel)
mc ls --recursive registro/registro-attachments | wc -l
```

**Anotar**: quantidade de arquivos no backup vs. bucket ativo. Devem ser iguais.

### 6. Limpar ambiente de teste

```bash
# Remover container e rede de teste
docker stop restore-test-db
docker rm restore-test-db
docker network rm restore-test-net

# Confirmar limpeza
docker ps -a | grep restore-test || echo "Ambiente de teste removido com sucesso"
```

---

## Checklist pos-restore

| # | Verificacao | Resultado |
|---|---|---|
| 1 | Dump lido sem erro de integridade (`pg_restore --list`) | OK / FALHA |
| 2 | Restore executou sem erros fatais | OK / FALHA |
| 3 | Tabelas principais tem registros (companies, users, work_orders) | OK / FALHA |
| 4 | Migration atualizada (`alembic_version` presente) | OK / FALHA |
| 5 | Usuarios admin existem e tem `password_hash` | OK / FALHA |
| 6 | Nao ha registros orfaos (sem `company_id`) | OK / FALHA |
| 7 | Backup MinIO tem mesma quantidade de arquivos que o bucket | OK / FALHA |
| 8 | Ambiente de teste foi removido por completo | OK / FALHA |

---

## Registro de execucoes

Apos cada teste, preencher uma linha na tabela abaixo.

| Data | Executor | Dump testado | Duracao | Resultado | Observacoes |
|---|---|---|---|---|---|
| 2026-07-05 | — | registro_20260705_030000.dump | — min | OK / FALHA | — |
| | | | | | |
| | | | | | |
| | | | | | |

---

## Troubleshooting

### Dump corrompido (`pg_restore --list` falha)

1. Verificar o checksum SHA-256: `sha256sum -c <dump>.sha256`
2. Se checksum falhou, o arquivo pode ter sido corrompido no disco. Tentar um dump anterior.
3. Verificar logs do service de backup: `docker service logs registro_backup --since 48h`

### Restore falha com erro de permissao

- Garantir que o usuario `registro` existe no container de teste (o `POSTGRES_USER=registro` cuida disso).
- Se houver objetos de outro owner, adicionar `--no-owner` ao `pg_restore`.

### Container de teste nao sobe

- Verificar espaco em disco: `df -h`
- Verificar se a porta 5432 nao esta em conflito (o container de teste nao expoe portas, mas verificar).

### Diferenca na contagem MinIO

- Pode haver arquivos novos criados apos o ultimo backup. A diferenca aceitavel e de ate 24h de uploads.
- Se a diferenca for grande, verificar logs: `docker service logs registro_backup-minio --since 48h`
