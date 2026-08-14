# Inventário de Anexos Físicos — V1 (Aero Hotel)

Mapeamento completo dos arquivos armazenados no servidor V1 (Laravel `storage/app/`)
para migração ao MinIO do GEOP V2.

## Resumo

O V1 usa disco `local` do Laravel (`storage/app/`), com symlink `public/storage → storage/app`.
Todos os uploads ficam no filesystem do servidor.

## Tabelas com colunas de arquivo

| # | Tabela MySQL | Coluna | Diretório em `storage/app/` | Tipo de arquivo | Modelo V2 destino |
|---|---|---|---|---|---|
| 1 | `users` | `image` | `images/` | Foto perfil (jpg/png) | `User.avatar_url` |
| 2 | `occurrences` | `file` | raiz (path completo) | Anexos diversos | `Occurrence.file` → MinIO |
| 3 | `procedures` | `file` | `procedure/` | PDFs, docs | `Procedure.file` → MinIO |
| 4 | `procedure_files` | `file` | `procedure/` | PDFs adicionais | `Procedure` attachments → MinIO |
| 5 | `shift_report_uploads` | `url_upload` | raiz (path completo) | Uploads turno | `ShiftReport` attachments → MinIO |
| 6 | `meeting_subject_attaches` | inline via `Storage::put` | `meeting_subject_attaches/` | Anexos de pauta | `MeetingSubject` attachments → MinIO |
| 7 | `work_diary_activities` | `attachment` | raiz (path completo) | Anexos diário | `ModuleRecord` (diario) → MinIO |
| 8 | `apartment_inspection` items | file | `anexo_apartment_inspection/` | Fotos/docs inspeção | `ModuleRecord` (inspecoes) → MinIO |
| 9 | `contract_specific_purposes` | file | `files/` | Contratos | futuro módulo contratos |
| 10 | `participants` | `url_image` | referência externa ou local | Fotos participantes | `MeetingParticipant` → MinIO |

## Diretórios esperados no servidor V1

```
/var/www/aero/storage/app/
├── images/                         # fotos de perfil de usuários
│   └── avatarDefaultBpd2020.jpg    # avatar padrão
├── procedure/                      # PDFs de procedimentos
├── meeting_subject_attaches/       # anexos de pautas de reunião
├── anexo_apartment_inspection/     # fotos/docs de inspeção de apartamento
├── files/                          # contratos
└── (raiz)                          # occurrences.file, shift_report_uploads, work_diary
```

## Plano de migração

### Pré-requisitos

1. Acesso SSH ao servidor V1 em produção
2. MinIO rodando no servidor de destino (já configurado via `app/core/storage.py`)
3. Dump MySQL atualizado já importado via `import_v1.py`

### Etapas

1. **Inventariar no servidor** — rodar no V1:
   ```bash
   find /var/www/aero/storage/app -type f | wc -l          # total de arquivos
   du -sh /var/www/aero/storage/app/                        # tamanho total
   du -sh /var/www/aero/storage/app/*/                      # por diretório
   ```

2. **Baixar o storage** — rsync do servidor V1:
   ```bash
   rsync -avz --progress user@v1-server:/var/www/aero/storage/app/ ./v1-storage/
   ```

3. **Rodar script de migração** — `api/scripts/migrate_v1_attachments.py`:
   - Lê as tabelas MySQL (ou PostgreSQL pós-import) para obter os paths dos arquivos
   - Para cada arquivo encontrado no filesystem local (`./v1-storage/`):
     - Faz upload para MinIO usando `storage.upload_file()`
     - Atualiza a coluna no PostgreSQL com a nova key MinIO
   - Gera relatório: migrados, não encontrados, falhas

4. **Validar** — comparar contagem de registros com `file IS NOT NULL` vs arquivos no MinIO

### Mapeamento de keys MinIO

Padrão: `{company_id}/{entity_type}/{entity_id}/{uuid}.{ext}`

| Entidade | `entity_type` no MinIO |
|---|---|
| User avatar | `user-avatar` |
| Occurrence file | `occurrence` |
| Procedure file | `procedure` |
| ShiftReport upload | `shift-report` |
| Meeting attachment | `meeting-subject` |
| Inspection file | `inspection` |
| WorkDiary attachment | `work-diary` |
| Contract file | `contract` |

## Riscos

- **Arquivos órfãos**: registros deletados (soft delete) ainda podem ter arquivos no disco
- **Arquivos ausentes**: coluna `file` preenchida mas arquivo físico não existe — listar no relatório
- **Nomes duplicados**: UUID na key MinIO evita colisões
- **Tamanho**: estimar antes de migrar para garantir espaço no MinIO
