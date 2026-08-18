# Integração Chess Hotel → Registro

> **[DESCONTINUADA em 2026-08-17]** Esta integração foi removida do código (endpoints, config, testes). Documento preservado como histórico de implementação; nada aqui reflete o comportamento atual do sistema.


Documentação para o desenvolvedor do Chess Hotel implementar a abertura de solicitações fiscais no Registro.

---

## Visão geral

O Chess Hotel envia solicitações fiscais para o Registro via API REST. O Registro resolve o usuário pelo e-mail, cria o ticket com SLA de 24h úteis e retorna o protocolo para acompanhamento.

**Fluxo:**
1. (Opcional) Resolver usuário por e-mail antes de abrir o chamado
2. Criar o ticket
3. Acompanhar o status do ticket pelo protocolo ou listar todos por e-mail

---

## Autenticação

Todos os endpoints exigem o header:

```
X-Registro-Key: <chave-de-integração>
```

A chave será fornecida pelo Registro. Em produção, deve ter no mínimo 32 caracteres.

Se a chave estiver ausente ou inválida, a API retorna:

```json
HTTP 401
{"code": "invalid_integration_key"}
```

---

## Base URL

| Ambiente        | URL                                          |
|-----------------|----------------------------------------------|
| Produção        | `https://geop.solidsd.com.br/api/v1`     |
| Desenvolvimento | `http://localhost:8000/api/v1`                |

---

## Endpoints

### 1. Resolver usuário (opcional)

Verifica se um e-mail existe no Registro antes de abrir o chamado.

```
POST /integrations/chess-hotel/users/resolve
```

**Headers:**
```
Content-Type: application/json
X-Registro-Key: <chave>
```

**Body:**
```json
{
  "email": "usuario@hotel.com"
}
```

**Resposta 200:**
```json
{
  "exists": true,
  "id": 42,
  "name": "João Silva",
  "email": "usuario@hotel.com"
}
```

**Erros:**

| Status | Código | Quando |
|--------|--------|--------|
| 401 | `invalid_integration_key` | Chave ausente ou inválida |
| 404 | `registro_user_not_found` | E-mail não encontrado no Registro |

---

### 2. Criar solicitação fiscal

```
POST /integrations/chess-hotel/tickets
```

**Headers:**
```
Content-Type: application/json
X-Registro-Key: <chave>
```

**Body:**
```json
{
  "module": "solicitacoes-fiscais",
  "requestType": "NF-e",
  "hotel": "aero-hotel",
  "solicitante": "João Silva",
  "solicitanteEmail": "joao@hotel.com",
  "chessUserId": "chess-user-123",
  "apartment": "204",
  "reservationNumber": "RES-2026-001",
  "origem": "chess-hotel"
}
```

**Campos:**

| Campo | Tipo | Obrigatório | Descrição |
|-------|------|:-----------:|-----------|
| `module` | string | sim | Sempre `"solicitacoes-fiscais"` |
| `requestType` | string | sim | Tipo da solicitação. Ex: `"NF-e"`, `"NFS-e"`, `"Recibo"` |
| `hotel` | string | sim | Slug do hotel no Registro. Será informado (ex: `"aero-hotel"`) |
| `solicitante` | string | sim | Nome de quem está solicitando |
| `solicitanteEmail` | string | sim | E-mail do solicitante. **Deve existir como usuário no Registro** |
| `chessUserId` | string | sim | ID do usuário no Chess Hotel (para rastreabilidade) |
| `apartment` | string | não | Número do apartamento/UH |
| `reservationNumber` | string | não | Número da reserva |
| `origem` | string | não | Default: `"chess-hotel"` |
| `screenshots` | string[] | não | Array de imagens em base64 (PNG/JPEG/WebP). Máximo 5 |

O body aceita campos extras (schema aberto). Campos adicionais são armazenados no payload para referência.

#### Screenshots (anexos de imagem)

O campo `screenshots` permite enviar capturas de tela junto com o chamado. As imagens são enviadas como strings **base64** (sem prefixo `data:image/...;base64,`).

| Regra | Valor |
|-------|-------|
| Máximo de screenshots | 5 por chamado |
| Formatos aceitos | PNG, JPEG, WebP |
| Tamanho máximo por imagem | 10 MB (após decode) |
| Detecção de formato | Automática (magic bytes) |

**Exemplo com screenshot:**
```json
{
  "module": "solicitacoes-fiscais",
  "requestType": "NF-e",
  "hotel": "aero-hotel",
  "solicitante": "João Silva",
  "solicitanteEmail": "joao@hotel.com",
  "chessUserId": "chess-42",
  "apartment": "204",
  "screenshots": [
    "iVBORw0KGgoAAAANSUhEUg...",
    "/9j/4AAQSkZJRgABAQ..."
  ]
}
```

Screenshots inválidos (formato não suportado, base64 malformado) são ignorados silenciosamente — o chamado é criado normalmente, apenas o anexo inválido não é salvo.

**Resposta 201:**
```json
{
  "protocol": "REG-000042",
  "status": "Em andamento",
  "responsible": null,
  "sla_deadline": "2026-06-24T18:00:00Z",
  "url": "https://geop.solidsd.com.br/solicitacoes-fiscais?protocol=REG-000042",
  "attachments_count": 2
}
```

**Erros:**

| Status | Código | Quando |
|--------|--------|--------|
| 401 | `invalid_integration_key` | Chave ausente ou inválida |
| 404 | `registro_user_not_found` | E-mail do solicitante não encontrado no Registro |
| 422 | `unsupported_module` | `module` diferente de `"solicitacoes-fiscais"` |
| 422 | `invalid_hotel` | `hotel` não corresponde ao slug configurado |
| 503 | `integration_company_not_found` | Empresa do Registro não encontrada (erro de configuração) |

---

### 3. Listar tickets por e-mail

Retorna todas as solicitações de um usuário (identificado pelo e-mail).

```
GET /integrations/chess-hotel/tickets?email=joao@hotel.com
```

**Headers:**
```
X-Registro-Key: <chave>
```

**Resposta 200:**
```json
{
  "user": {
    "exists": true,
    "id": 42,
    "name": "João Silva",
    "email": "joao@hotel.com"
  },
  "items": [
    {
      "protocol": "REG-000042",
      "request_type": "NF-e",
      "status": "Em andamento",
      "responsible": "Maria Souza",
      "sla_deadline": "2026-06-24T18:00:00Z",
      "completed": false,
      "updated_at": "2026-06-22T14:30:00Z",
      "url": "https://geop.solidsd.com.br/solicitacoes-fiscais?protocol=REG-000042",
      "history": [
        {
          "event": "create_from_chess",
          "user": "João Silva",
          "at": "2026-06-22T10:00:00Z",
          "changes": null
        },
        {
          "event": "update",
          "user": "Maria Souza",
          "at": "2026-06-22T14:30:00Z",
          "changes": {"status": ["Em andamento", "Concluído"]}
        }
      ]
    }
  ]
}
```

**Erros:**

| Status | Código | Quando |
|--------|--------|--------|
| 401 | `invalid_integration_key` | Chave ausente ou inválida |
| 404 | `registro_user_not_found` | E-mail não encontrado |

---

### 4. Consultar ticket por protocolo

```
GET /integrations/chess-hotel/tickets/{protocol}?email=joao@hotel.com
```

**Headers:**
```
X-Registro-Key: <chave>
```

**Resposta 200:**
```json
{
  "protocol": "REG-000042",
  "request_type": "NF-e",
  "status": "Concluído",
  "responsible": "Maria Souza",
  "sla_deadline": "2026-06-24T18:00:00Z",
  "completed": true,
  "updated_at": "2026-06-23T09:15:00Z",
  "url": "https://geop.solidsd.com.br/solicitacoes-fiscais?protocol=REG-000042",
  "history": [
    {
      "event": "create_from_chess",
      "user": "João Silva",
      "at": "2026-06-22T10:00:00Z",
      "changes": null
    }
  ]
}
```

**Erros:**

| Status | Código | Quando |
|--------|--------|--------|
| 401 | `invalid_integration_key` | Chave ausente ou inválida |
| 404 | `registro_user_not_found` | E-mail não encontrado |
| 404 | `ticket_not_found` | Protocolo não existe ou não pertence a esse usuário |

---

## Rate Limiting

Os endpoints de criação e resolução de usuário têm limite de **30 requisições por minuto** por IP.

Se excedido, retorna `HTTP 429 Too Many Requests`.

---

## Configuração no Chess Hotel

Para conectar o Chess Hotel ao Registro, o desenvolvedor precisa configurar:

| Configuração | Valor |
|-------------|-------|
| **URL da API** | `https://geop.solidsd.com.br/api/v1` |
| **Header de autenticação** | `X-Registro-Key` |
| **Chave de integração** | Será fornecida (string com 32+ caracteres) |
| **Slug do hotel** | `"aero-hotel"` |
| **Módulo** | Sempre `"solicitacoes-fiscais"` |

### O que precisa ser implementado no Chess Hotel

1. **Armazenar a chave de integração** em variável de ambiente ou config segura (não hardcoded)
2. **Na tela de solicitação fiscal**, montar o request com os campos do hóspede/solicitante e enviar via `POST /integrations/chess-hotel/tickets`
3. **Guardar o protocolo retornado** (`REG-XXXXXX`) para referência e exibição ao usuário
4. **Opcional — tela de acompanhamento**: consultar status via `GET /integrations/chess-hotel/tickets?email=...` ou `GET /integrations/chess-hotel/tickets/{protocol}?email=...`
5. **Tratar os erros** listados em cada endpoint (401, 404, 422, 429, 503)

### Mapeamento de campos Chess → Registro

| No Chess Hotel | Campo no request | Exemplo |
|----------------|-----------------|---------|
| Nome do solicitante | `solicitante` | `"João Silva"` |
| E-mail do solicitante | `solicitanteEmail` | `"joao@hotel.com"` |
| ID do usuário no Chess | `chessUserId` | `"chess-42"` |
| Tipo de documento fiscal | `requestType` | `"NF-e"`, `"NFS-e"`, `"Recibo"` |
| Apartamento / UH | `apartment` | `"204"` |
| Número da reserva | `reservationNumber` | `"RES-2026-001"` |
| CPF/CNPJ do tomador | `taxpayerDoc` (dentro do body) | `"123.456.789-00"` |
| E-mail do tomador | `taxpayerEmail` (dentro do body) | `"tomador@email.com"` |
| Prints de tela | `screenshots` | Array de base64 (ver seção Screenshots) |

### Pré-requisitos

1. **Chave de integração** — será fornecida pelo Registro
2. **Slug do hotel** — `"aero-hotel"` (fixo por enquanto)
3. **Usuários sincronizados** — o e-mail usado no `solicitanteEmail` precisa existir como usuário ativo no Registro. Se não existir, o endpoint retorna 404. Garantir que os mesmos e-mails estejam cadastrados em ambos os sistemas

---

## Exemplo completo (cURL)

### Criar ticket

```bash
curl -X POST https://geop.solidsd.com.br/api/v1/integrations/chess-hotel/tickets \
  -H "Content-Type: application/json" \
  -H "X-Registro-Key: sua-chave-de-integracao-aqui" \
  -d '{
    "module": "solicitacoes-fiscais",
    "requestType": "NF-e",
    "hotel": "aero-hotel",
    "solicitante": "João Silva",
    "solicitanteEmail": "joao@hotel.com",
    "chessUserId": "chess-42",
    "apartment": "204",
    "reservationNumber": "RES-2026-001"
  }'
```

### Consultar tickets do usuário

```bash
curl "https://geop.solidsd.com.br/api/v1/integrations/chess-hotel/tickets?email=joao@hotel.com" \
  -H "X-Registro-Key: sua-chave-de-integracao-aqui"
```

### Consultar ticket específico

```bash
curl "https://geop.solidsd.com.br/api/v1/integrations/chess-hotel/tickets/REG-000042?email=joao@hotel.com" \
  -H "X-Registro-Key: sua-chave-de-integracao-aqui"
```

---

## Validações

- **E-mail**: normalizado (lowercase, trim). Formato validado.
- **CPF/CNPJ**: se enviado no payload como `taxpayerDoc`, é validado e normalizado.
- **E-mail do tomador**: se enviado no payload como `taxpayerEmail`, é validado.
- **SLA**: 24 horas úteis (dias úteis, horário comercial, timezone do hotel). Calculado automaticamente pelo Registro.

---

## Notas

- O protocolo retornado (`REG-XXXXXX`) é a referência para acompanhamento
- O campo `url` na resposta aponta para a tela do ticket no Registro
- O `history` retorna o histórico completo de eventos (criação, atualizações, mudanças de status)
- Solicitações criadas via Chess Hotel notificam automaticamente todos os usuários ativos do módulo fiscal no Registro (in-app, e-mail e WhatsApp conforme configurado)
