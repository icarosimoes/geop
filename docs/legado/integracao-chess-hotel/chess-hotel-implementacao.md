# Integração Chess Hotel → GEOP — Guia de implementação em produção

> **[DESCONTINUADA em 2026-08-17]** Esta integração foi removida do código (endpoints, config, testes). Documento preservado como histórico de implementação; nada aqui reflete o comportamento atual do sistema.


## Objetivo

Permitir que a recepção e outros setores do hotel abram chamados no sistema GEOP diretamente de dentro do Chess Hotel (front) e Chess Gestão (back), sem sair do PMS. Os chamados são de dois tipos:

- **Solicitação Fiscal** — problemas com emissão de notas fiscais (recepção → financeiro)
- **Chamado de Manutenção** — solicitações corretivas, preventivas ou emergenciais

O Chess Hotel **não é modificado estruturalmente**. A integração consiste em **um componente Vue adicionado ao layout** e **uma variável de ambiente** apontando para a API do GEOP.

---

## Infraestrutura atual do Chess Hotel

| Item | Valor |
| --- | --- |
| Stack | Laravel 7 + Vue.js (Composition API) + Vuetify 2 |
| SPA | `/spa/src/` |
| API produção | `https://api.aerohotel.chesshotel.ocatech.com.br/api/` |
| WebSocket | `https://ws.chesshotel.ocatech.com.br` |
| Homologação | `https://api-hom.aerohotel.chesshotel.ocatech.com.br/api/` |
| Axios | `spa/src/plugins/axios.js` — instância com `baseURL` via `VUE_APP_URL_API`, interceptors de auth (Bearer token em `localStorage.accessToken`) e tratamento de 401 |
| Vuex login | `spa/src/store/login/login.js` — `state.user` contém `{ name, role: { name, permission } }` |
| Rota de quartos | `/manager_room/:room_id?` — param `room_id` disponível em `$route.params.room_id` |
| Layout principal | `spa/src/layouts/variants/content/vertical-nav/LayoutContentVerticalNav.vue` |

---

## Arquivos envolvidos

### Criar

| Arquivo | Descrição |
| --- | --- |
| `spa/src/components/RegistroLauncher.vue` | Componente completo: botão, dropdown, drawer com formulários |

### Modificar

| Arquivo | Alteração |
| --- | --- |
| `spa/src/layouts/variants/content/vertical-nav/LayoutContentVerticalNav.vue` | Importar e posicionar `RegistroLauncher` |
| `spa/.env.production` | Adicionar `VUE_APP_REGISTRO_API_URL` |
| `spa/.env.hom` | Adicionar `VUE_APP_REGISTRO_API_URL` |

---

## Passo a passo

### 1. Copiar o componente

Copiar o arquivo `RegistroLauncher.vue` para `spa/src/components/`.

O componente já existe no repositório de desenvolvimento em:
```
/home/icarosimoes/dev/chess-hotel/spa/src/components/RegistroLauncher.vue
```

### 2. Registrar no layout

Abrir `spa/src/layouts/variants/content/vertical-nav/LayoutContentVerticalNav.vue`.

**Adicionar o import** (junto aos outros imports de componentes):
```js
import RegistroLauncher from '@/components/RegistroLauncher.vue'
```

**Registrar no `components`**:
```js
components: {
  LayoutContentVerticalNav,
  AppBarUserMenu,
  RegistroLauncher,  // ← adicionar
  SearchBar,
},
```

**Posicionar no template** — dentro do `right-row`, antes do `app-bar-user-menu`:
```html
<div class="d-flex align-center right-row">
  <registro-launcher></registro-launcher>
  <app-bar-user-menu></app-bar-user-menu>
</div>
```

### 3. Configurar variável de ambiente

Adicionar nos arquivos `.env`:

**`.env.hom`**:
```
VUE_APP_REGISTRO_API_URL=https://registro-api-hom.dominio.com.br/api/v1/chamados
```

**`.env.production`**:
```
VUE_APP_REGISTRO_API_URL=https://registro-api.dominio.com.br/api/v1/chamados
```

> Substituir pelos domínios reais quando o GEOP estiver em produção. Enquanto a variável não existir ou a URL não responder, o componente automaticamente salva os chamados em `localStorage` (chave `registro_pending_tickets`) para sincronização futura.

### 4. Rebuild e deploy

```bash
cd spa
npm run build -- --mode production   # ou --mode hom
```

Substituir o conteúdo de `/dist` no servidor de produção do Chess Hotel.

---

## Comportamento do componente

### Fluxo do usuário

1. Usuário logado no Chess vê um botão com ícone de clipboard (laranja) no navbar, à esquerda do avatar.
2. Ao clicar, aparece um dropdown com duas opções: "Solicitação Fiscal" e "Chamado de Manutenção".
3. Ao selecionar, abre um drawer lateral direito (480px) com formulário específico.
4. O formulário pré-preenche automaticamente:
   - **Nome do solicitante** — vem de `this.$store.getters['login/getUser'].name`
   - **UH/Apartamento** — vem de `this.$route.params.room_id` (quando o usuário está na tela de gestão de quartos)
5. Ao enviar, o componente faz `POST` para `VUE_APP_REGISTRO_API_URL` com payload JSON.
6. Exibe snackbar com protocolo (`REG-{timestamp}`) e fecha o drawer.

### Formulário de Solicitação Fiscal

Possui um dropdown "Tipo de solicitação" que controla quais campos aparecem:

| Tipo | Campos dinâmicos |
| --- | --- |
| Dados do tomador incorretos | Nº reserva, CNPJ/CPF correto, nome correto, endereço correto, detalhes da correção |
| Nota travada / erro no sistema | Nº da nota tentada, descrição do erro, print do erro (arquivo, obrigatório) |
| Nota solicitada após check-out | Nº reserva, data check-out, nome do tomador, CNPJ/CPF, endereço, e-mail |
| Cancelamento de nota emitida | Nº da nota fiscal, motivo do cancelamento |

Campos comuns a todos: UH/Apartamento, observações, anexos adicionais.

### Formulário de Chamado de Manutenção

Campos fixos: título, categoria (Preventiva/Corretiva/Emergencial), local, UH, prioridade (Baixa/Normal/Alta/Urgente), descrição, anexos.

### Fallback offline

Se `VUE_APP_REGISTRO_API_URL` não estiver configurado ou o POST falhar, o chamado é salvo em `localStorage` sob a chave `registro_pending_tickets` como array JSON. Cada item contém:

```json
{
  "module": "solicitacoes-fiscais",
  "requestType": "Dados do tomador incorretos",
  "apartment": "412",
  "solicitante": "João Silva",
  "origem": "chess-hotel",
  "protocol": "REG-1750456800000",
  "createdAt": "2026-06-20T18:00:00.000Z",
  ...campos específicos do tipo
}
```

---

## Contrato da API do GEOP (implementado)

O endpoint de solicitações fiscais já está implementado:

```
POST /api/v1/integrations/chess-hotel/tickets
Content-Type: application/json
X-Registro-Key: {CHESS_HOTEL_INTEGRATION_KEY}
```

O header `X-Registro-Key` autentica a integração. O tenant é resolvido pelo slug configurado em `CHESS_HOTEL_COMPANY_SLUG` (padrão: `aero-hotel`).

> **Nota**: a URL no `.env` do Chess deve apontar para `/api/v1/integrations/chess-hotel/tickets`, não `/api/v1/chamados` como referenciado anteriormente.

### Payload

```json
{
  "module": "solicitacoes-fiscais",
  "solicitante": "string (nome do usuário no Chess)",
  "origem": "chess-hotel",
  "apartment": "string (UH)",
  "requestType": "string (um dos 4 tipos)",
  "reservationNumber": "string",
  "invoiceNumber": "string",
  "checkoutDate": "string (dd/mm/aaaa)",
  "taxpayerDoc": "string (CPF ou CNPJ)",
  "taxpayerName": "string",
  "taxpayerAddress": "string",
  "taxpayerEmail": "string",
  "cancellationReason": "string",
  "correction": "string",
  "observations": "string"
}
```

Campos presentes dependem do `requestType`. Campos ausentes vêm como string vazia ou não são enviados. O campo `module` deve ser `solicitacoes-fiscais` (manutenção ainda não é suportada pela integração). Todos os campos extras são armazenados no campo `payload` (JSON) do registro.

### Resposta

**Sucesso (200)**:
```json
{
  "protocol": "REG-000001"
}
```

O componente exibe o `protocol` no snackbar. Se a resposta não contiver `protocol`, gera um local (`REG-{timestamp}`).

**Erro (4xx/5xx)**: qualquer status diferente de 2xx dispara o fallback localStorage.

| Código HTTP | Causa |
| --- | --- |
| 401 | `X-Registro-Key` ausente ou inválido |
| 422 | `module` diferente de `solicitacoes-fiscais` |
| 503 | tenant configurado não encontrado ou inativo |

---

## Autenticação cross-system

O Chess Hotel usa Bearer token (JWT) gerado pelo Laravel, armazenado em `localStorage.accessToken`. O GEOP usa seu próprio JWT.

**Opções para autenticação entre os dois sistemas** (escolher uma):

### Opção A — Token de serviço (recomendada para MVP)

1. Criar no Registro um token de API de longa duração vinculado ao tenant `aero-hotel`.
2. Configurar como variável de ambiente no Chess: `VUE_APP_REGISTRO_TOKEN`.
3. O componente envia no header: `Authorization: Bearer {token}`.
4. **Prós**: simples, sem mudança no fluxo de login. **Contras**: token fixo, sem identificação individual do usuário no Registro (o nome vai no payload como `solicitante`).

### Opção B — SSO / token exchange

1. Ao logar no Chess, fazer um request adicional ao Registro trocando o token Chess por um token Registro.
2. Armazenar o token Registro em `localStorage.registroToken`.
3. O componente usa esse token no header.
4. **Prós**: identifica o usuário individualmente no Registro. **Contras**: requer endpoint de token exchange e lógica de refresh.

### Opção C — Proxy via Laravel do Chess

1. Criar uma rota no Laravel do Chess (`POST /api/registro/chamados`) que faz proxy para a API do Registro.
2. O componente usa o axios do Chess (que já tem o Bearer token) para bater na rota local.
3. O Laravel do Chess se autentica com o Registro via service-to-service token.
4. **Prós**: sem CORS, sem token exposto no front. **Contras**: o Chess precisa de alteração no backend.

---

## CORS

Se o Chess Hotel e o Registro estão em domínios diferentes (provável), o Registro precisa aceitar requests do domínio do Chess:

```python
# FastAPI - middleware CORS
origins = [
    "https://aerohotel.chesshotel.ocatech.com.br",
    "https://hom.aerohotel.chesshotel.ocatech.com.br",
]
```

Se a Opção C (proxy) for escolhida, CORS não é necessário.

---

## Checklist de deploy

- [ ] Copiar `RegistroLauncher.vue` para `spa/src/components/`
- [ ] Alterar `LayoutContentVerticalNav.vue` (import + template + components)
- [ ] Adicionar `VUE_APP_REGISTRO_API_URL` em `.env.hom` e `.env.production`
- [ ] Definir estratégia de autenticação (A, B ou C)
- [ ] Se opção A: gerar token de serviço no Registro e adicionar `VUE_APP_REGISTRO_TOKEN` nos `.env`
- [x] Implementar `POST /api/v1/integrations/chess-hotel/tickets` no Registro (FastAPI)
- [ ] Configurar CORS no Registro para aceitar o domínio do Chess
- [ ] Testar em homologação: abrir chamado fiscal e de manutenção
- [ ] Verificar que chamados aparecem no módulo "Solicitações Fiscais" do Registro
- [ ] Testar fallback: desligar API do Registro, abrir chamado, verificar `localStorage`
- [ ] Build e deploy do SPA do Chess em produção
- [ ] Monitorar `registro_pending_tickets` no localStorage dos terminais da recepção

---

## Riscos e mitigações

| Risco | Impacto | Mitigação |
| --- | --- | --- |
| API do Registro fora do ar | Chamados não são persistidos no servidor | Fallback localStorage + sincronização futura |
| Token de serviço vazado | Acesso não autorizado ao Registro | Restringir token por IP ou rotacionar periodicamente |
| Recepcionista limpa localStorage | Chamados pendentes perdidos | Implementar sincronização automática ao reconectar |
| CORS bloqueado em produção | Componente não consegue enviar | Testar em homologação antes; alternativa: proxy Laravel |
| Atualização do Chess sobrescreve o componente | Launcher desaparece | Documentar alteração; incluir no checklist de atualização do PMS |

---

## Evolução futura

1. **Sincronização de pendentes**: ao detectar que a API do Registro voltou, enviar automaticamente os chamados do `localStorage`.
2. **Notificações bidirecionais**: Chess recebe webhook quando o chamado muda de status no Registro.
3. **Pré-preenchimento expandido**: buscar dados da reserva ativa via `helper/get_reserves` para preencher nome do hóspede, CNPJ e número da reserva automaticamente.
4. **Widget de status**: mostrar no Chess um badge com quantidade de chamados abertos do usuário no Registro.
5. **Chess Gestão**: instalar o mesmo componente no backoffice para que o financeiro veja e responda chamados sem sair do Chess Gestão.
