# Padrão de paginação da API

## Quando usar offset vs cursor

| Critério | Offset (`?page=N&page_size=M`) | Cursor (`?cursor=X`) |
|---|---|---|
| Caso de uso | Listagens gerais, tabelas com paginação numérica | Feeds, timelines, scroll infinito |
| Performance | O(N) com offset grande | O(1) constante |
| Estabilidade | Pode pular/repetir itens se dados mudam entre páginas | Estável mesmo com inserções/remoções |
| Navegação | Permite ir direto a qualquer página | Apenas próximo/anterior |
| Total | Retorna `total` para UI de "página X de Y" | Não retorna total |

### Regra prática

- **Offset**: qualquer endpoint de listagem em CRUD administrativo (tabelas, modais de seleção).
- **Cursor**: timelines, notificações, feeds de atividades, logs — qualquer lista que cresce em tempo real.

## Formato de resposta

### Offset

```json
{
  "items": [...],
  "total": 142,
  "page": 2,
  "page_size": 20
}
```

Parâmetros: `page` (≥1), `page_size` (1-100, default 20).

### Cursor

```json
{
  "items": [...],
  "next_cursor": "eyJpZCI6...",
  "has_more": true
}
```

Parâmetro: `cursor` (opaco, base64 de `{id, timestamp}`). Primeira chamada sem cursor retorna os mais recentes.

## Endpoints que suportam cursor

- `GET /work-orders/cursor`
- `GET /timeline/{entity_type}/{entity_id}/cursor`

Todos os outros endpoints usam offset.

## Implementação

- Utilitário: `app/core/pagination.py` — `encode_cursor()`, `decode_cursor()`
- O cursor codifica o `id` e `created_at`/`updated_at` do último item retornado
- Ordenação sempre por `(campo_data DESC, id DESC)` para determinismo
