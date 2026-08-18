# Versionamento da API

## Estratégia

A API usa **versionamento por prefixo de URL**: `/api/v1`, `/api/v2`, etc.

Essa abordagem foi escolhida por ser a mais simples de implementar, debugar e documentar. Clients apontam para a versão que suportam; o servidor pode manter múltiplas versões em paralelo.

## Infraestrutura atual

Em `main.py`, todos os routers são agrupados sob um `v1_router`:

```python
v1_router = APIRouter(prefix="/api/v1")
v1_router.include_router(health_router)
v1_router.include_router(work_orders_router)
# ...
app.include_router(v1_router)
```

Para criar uma v2, basta criar um `v2_router` com os routers alterados e montar ambos no `app`.

## Quando criar v2

Criar nova versão **apenas** quando houver breaking change:

- Remoção ou renomeação de campo obrigatório em request/response
- Mudança de tipo de campo (ex: `string` → `int`)
- Remoção de endpoint
- Mudança de semântica de parâmetro existente

**Não é breaking change** (não precisa de v2):

- Adicionar campo opcional em request
- Adicionar campo em response
- Adicionar novo endpoint
- Adicionar novo query parameter opcional

## Regras de coexistência

1. **v1 permanece estável** enquanto houver clients ativos (frontend web, admin, colaborador).
2. **v2 pode importar do v1** — endpoints não alterados podem ser re-exportados.
3. **Deprecação**: quando v2 estiver completa, v1 recebe header `Deprecation: true` e `Sunset: <data>` nas respostas. Prazo mínimo de 90 dias.
4. **Remoção**: v1 só é removida quando não houver tráfego ativo.

## Exemplo de adição de v2

```python
from fastapi import APIRouter

v2_router = APIRouter(prefix="/api/v2")

# Endpoints inalterados — reutilizar do v1
v2_router.include_router(health_router)
v2_router.include_router(auth_router)

# Endpoints com breaking changes — usar versão nova
v2_router.include_router(work_orders_v2_router)

app.include_router(v1_router)
app.include_router(v2_router)
```
