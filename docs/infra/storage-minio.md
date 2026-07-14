# Storage — MinIO (S3)

O Registro usa MinIO self-hosted como object storage para anexos de todos os tenants. A API se comunica via protocolo S3 (boto3).

## Arquitetura

```
Usuário → API (FastAPI) → MinIO (S3)
                              │
                        registro-attachments/
                        ├── {company_id}/
                        │   ├── work_order/{entity_id}/{uuid}.pdf
                        │   ├── fiscal_request/{entity_id}/{uuid}.jpg
                        │   ├── procedure/{entity_id}/{uuid}.pdf
                        │   └── module_record/{entity_id}/{uuid}.png
                        └── ...
```

Cada arquivo é armazenado com chave `{company_id}/{entity_type}/{entity_id}/{uuid}.{ext}`. O `company_id` na chave garante isolamento por tenant no nível de storage.

## Configuração

### Desenvolvimento local (Docker Compose)

O MinIO sobe automaticamente com `docker compose up`:

| Serviço | URL | Credenciais |
| --- | --- | --- |
| API S3 | `http://localhost:9000` | `registro` / `registro-dev-secret` |
| Console web | `http://localhost:9001` | mesmas credenciais |

### Produção (Docker Swarm)

O MinIO roda como serviço no stack, fixado no nó manager:

| Item | Valor |
| --- | --- |
| Imagem | `minio/minio:RELEASE.2025-09-07T16-13-09Z` |
| Rede | `registro-internal` (overlay) |
| Volume | `registro-minio-data` |
| Bucket | `registro-attachments` |
| Credenciais | Docker Secrets (`registro_s3_access_key`, `registro_s3_secret_key`) |

A API conecta ao MinIO via `http://minio:9000` (rede interna). O bucket é criado automaticamente no startup da API (`ensure_bucket()`).

### Variáveis da API

| Variável | Default (dev) | Produção |
| --- | --- | --- |
| `S3_ENDPOINT_URL` | `http://localhost:9000` | `http://minio:9000` |
| `S3_ACCESS_KEY` | `registro` | via `S3_ACCESS_KEY_FILE` (secret) |
| `S3_SECRET_KEY` | `registro-dev-secret` | via `S3_SECRET_KEY_FILE` (secret) |
| `S3_BUCKET` | `registro-attachments` | `registro-attachments` |
| `S3_PUBLIC_URL` | `http://localhost:9000` | `https://{REGISTRO_WEB_HOST}` |
| `ATTACHMENT_MAX_SIZE_MB` | `10` | `10` |

## Endpoints da API

| Método | Endpoint | Descrição |
| --- | --- | --- |
| `POST` | `/api/v1/attachments?entity_type=X&entity_id=Y` | Upload (multipart form) |
| `GET` | `/api/v1/attachments?entity_type=X&entity_id=Y` | Listar anexos da entidade |
| `GET` | `/api/v1/attachments/{id}/download` | Download do arquivo |
| `DELETE` | `/api/v1/attachments/{id}` | Excluir anexo |

### Tipos de entidade suportados

- `work_order` — Ordens de serviço (absorveu Ocorrências em 2026-07-14)
- `fiscal_request` — Solicitações fiscais
- `procedure` — Procedimentos
- `module_record` — Registros de módulo (inspeções, diário, etc.)

### Tipos de arquivo permitidos

Imagens: jpg, png, gif, webp, svg | Documentos: pdf, doc, docx, xls, xlsx, csv, txt | Compactados: zip, rar, 7z

Limite: 20 anexos por entidade, 10 MB por arquivo. Validação por extensão, content-type e magic bytes.

## Verificação em produção

```bash
# Status do serviço
docker service ls | grep minio

# Logs
docker service logs --tail 50 registro_minio

# Testar conectividade de dentro da API
docker exec $(docker ps -q -f "name=registro_api" | head -1) \
  python -c "from app.core.storage import ensure_bucket; ensure_bucket(); print('OK')"

# Listar objetos no bucket (de dentro do container MinIO)
docker exec $(docker ps -q -f "name=registro_minio" | head -1) \
  mc alias set local http://localhost:9000 \$(cat /run/secrets/registro_s3_access_key) \$(cat /run/secrets/registro_s3_secret_key) && \
  mc ls local/registro-attachments/ --recursive
```

## Backup

O volume `registro-minio-data` contém todos os arquivos. O backup do PostgreSQL (serviço `registro_backup`) **não inclui** os arquivos do MinIO — são sistemas separados.

Para backup do MinIO:

```bash
# Snapshot do volume (no nó manager)
docker run --rm -v registro-minio-data:/data -v /backups:/backup alpine \
  tar czf /backup/minio_$(date +%Y%m%d).tar.gz /data
```

## Migração de anexos V1

Os anexos do sistema legado (Laravel) estão no filesystem do servidor antigo, não no MinIO. O inventário completo está em [inventario-anexos-v1.md](../inventario-anexos-v1.md). A migração desses arquivos para o MinIO é um procedimento separado da importação de dados do banco — o script `import-v1-swarm.sh` só migra dados, não arquivos.

## Validado em 22/06/2026

Upload, listagem, download e delete testados com sucesso no ambiente de produção (`registro.solidsd.com.br`). MinIO respondendo corretamente na rede interna do Swarm.
