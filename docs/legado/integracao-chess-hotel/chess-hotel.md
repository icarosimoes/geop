# Integração Chess Hotel ↔ GEOP

> **[DESCONTINUADA em 2026-08-17]** Esta integração foi removida do código (endpoints, config, testes). Documento preservado como histórico de implementação; nada aqui reflete o comportamento atual do sistema.


## Contexto

O Chess Hotel é o PMS (Property Management System) hoteleiro usado pela operação. Possui dois módulos:

- **Chess Hotel** (front) — recepção, reservas, check-in/out
- **Chess Gestão** (back) — backoffice financeiro e administrativo

O GEOP não substitui nem duplica funcionalidades do Chess. A integração existe para **documentar e rastrear a comunicação entre recepção e financeiro** quando há problemas com emissão de notas fiscais, e para abrir chamados de manutenção.

## Arquitetura

A integração cria chamados no GEOP e permite que o Chess consulte seu andamento. O GEOP não modifica dados operacionais do Chess.

## Identidade e acompanhamento

O Chess usa seu backend Laravel como proxy e nunca expõe a chave de integração no navegador. Antes de abrir uma solicitação, o Laravel consulta `POST /api/v1/integrations/chess-hotel/users/resolve` com o e-mail do usuário autenticado. A criação só é aceita quando existe um usuário ativo com o mesmo e-mail no tenant configurado.

As solicitações enviam o ID do usuário no Chess, e-mail, hotel, reserva e origem. O acompanhamento usa `GET /api/v1/integrations/chess-hotel/tickets?email=...` ou `GET /api/v1/integrations/chess-hotel/tickets/{protocol}?email=...` e retorna status, responsável, SLA, histórico, conclusão e URL do protocolo no GEOP.

Em produção, `CHESS_HOTEL_INTEGRATION_KEY` deve ser um segredo com pelo menos 32 caracteres e compartilhado apenas entre os backends. Também são obrigatórios `CHESS_HOTEL_COMPANY_SLUG` e `REGISTRO_WEB_URL` no Registro, além de `REGISTRO_API_URL`, `REGISTRO_API_KEY`, `REGISTRO_HOTEL_SLUG` e `REGISTRO_WEB_URL` no Laravel do Chess.

```
Chess Hotel (Vue/Vuetify)
  └─ RegistroLauncher.vue (navbar)
       ├─ Solicitação Fiscal → POST /api/v1/fiscal-requests (futuro)
       └─ Chamado de Manutenção → POST /api/v1/work-orders (futuro)
```

## Componentes no Chess Hotel

Repositório: `/home/icarosimoes/dev/chess-hotel`

| Arquivo | Função |
| --- | --- |
| `spa/src/components/RegistroLauncher.vue` | Botão no navbar, dropdown de tipo, drawer com formulário |
| `spa/src/layouts/.../LayoutContentVerticalNav.vue` | Layout modificado para incluir o launcher |

## Launcher — comportamento

1. Botão laranja (ícone clipboard) no navbar, antes do menu do usuário.
2. Ao clicar, dropdown com duas opções: Solicitação Fiscal ou Chamado de Manutenção.
3. Ao selecionar, abre drawer lateral (480px) com formulário específico.
4. Auto-captura do contexto: nome do usuário (Vuex `login/getUser`), UH da rota (`$route.params.room_id`).
5. Envia POST para `VUE_APP_REGISTRO_API_URL`. Se falhar ou não estiver configurado, salva em `localStorage` sob `registro_pending_tickets`.
6. Exibe snackbar com protocolo (`REG-{timestamp}`) e fecha o drawer.

## Tipos de solicitação fiscal

| Tipo | Campos específicos |
| --- | --- |
| Dados do tomador incorretos | Nº reserva, CNPJ/CPF, nome, endereço, correção |
| Nota travada / erro no sistema | Nº da nota, descrição do erro, print (anexo obrigatório) |
| Nota solicitada após check-out | Nº reserva, data check-out, dados completos do tomador |
| Cancelamento de nota emitida | Nº da nota, motivo do cancelamento |

Campos comuns: UH/apartamento, observações, anexos.

## Pendências

- [ ] Criar endpoints no GEOP para receber chamados do Chess (autenticação por token de serviço)
- [ ] Configurar `VUE_APP_REGISTRO_API_URL` no ambiente do Chess
- [ ] Definir autenticação cross-system (SSO, token compartilhado ou login embarcado)
- [ ] Implementar fila de sincronização para tickets salvos em localStorage quando offline
- [ ] Testar CORS entre domínios Chess e GEOP em produção
