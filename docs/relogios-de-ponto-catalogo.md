# Catálogo de relógios de ponto — integração com o Registro

## Objetivo

Levantar os relógios de ponto/biométricos mais usados no Brasil e mapear como cada um
expõe as batidas, para decidir a ordem de suporte no **agente local** (`/agent`, Go) que
faz a ponte entre o equipamento (rede local) e o backend do Registro
(`POST /integrations/control-id/{webhook_token}/punches`, já implementado em
`api/app/domain/timeclock/webhook_router.py` — ver [docs/integracao-escala-ponto.md](integracao-escala-ponto.md)).

O backend já é agnóstico de marca: qualquer fonte que normalize um evento para
`{external_id, punched_at, type, event_id}` funciona. O trabalho de catalogar é
descobrir **como extrair esse evento de cada equipamento**.

## Comparativo

| Marca / linha | Popularidade no Brasil | Forma de integração | Protocolo | Homologado INMETRO/MTE (REP-P) | Prioridade |
|---|---|---|---|---|---|
| **Control iD** (iDFace, iDBlock Next, iDAccess) | Muito alta em condomínios, hotéis e empresas médias — fabricante nacional (Campinas/SP), forte em biometria facial | REST HTTP local (`login.fcgi`, `load_objects.fcgi`, `get_catalog.fcgi`) + push webhook configurável no próprio equipamento | HTTP/JSON, sessão via cookie | Linhas iDClass são REP-P; iDFace/iDBlock são controle de acesso (não fiscal) | **1 (implementado no agente)** |
| **ZKTeco** (iFace, SpeedFace, MB-series) | Altíssima — líder global, muito comum em pequenas empresas por preço | Protocolo binário proprietário TCP/UDP porta 4370 (bem documentado por engenharia reversa: projeto `zkteco/zkteco` / `pyzk`); linhas novas também têm push HTTP (ADMS) | TCP binário (zklib) ou HTTP ADMS (`iclock/cdata`) | Não é REP-P nativamente (depende de linha) | 2 |
| **Henry** (Ponto Fácil, Colmeia, Cronos) | Alta — tradicional em RH/consultorias de departamento pessoal, forte em conformidade | Arquivo **AFD** (Portaria 1.510/671 do MTE) exportado por USB/rede + push HTTP em modelos novos | Arquivo-texto AFD (layout fixo por campo) ou HTTP | **Sim — linha é o padrão REP-P/REP-C do MTE** | 3 |
| **Topdata** (Topdata REP, inFinger) | Alta — forte em varejo e indústria | AFD + integração via middleware próprio (TopSoft) | AFD / SDK Windows (.dll) | Sim (REP-P) | 4 |
| **Madis** (Ponto Secullum compatível) | Média-alta — muito usada via software Secullum | Arquivo AFD + REST em modelos IP | AFD / HTTP | Sim (REP-P) | 4 |
| **Nitgen / Dimep** | Média | AFD, alguns com SDK proprietário | AFD / SDK | Parcial (Dimep tem linha REP-P) | 5 (avaliar sob demanda) |

### Por que Control iD primeiro

- Já existe suporte no backend (`TimeClockDevice.model` default `"control_id"`, webhook dedicado).
- API REST local documentada publicamente (não exige engenharia reversa de protocolo binário).
- Forte presença em hotéis pequenos/médios — perfil de cliente do Registro.
- Permite dois modos de operação, cobrindo os dois cenários de rede do cliente:
  1. **Push nativo**: o próprio equipamento é configurado para enviar HTTP POST direto para
     `https://<tenant>.../integrations/control-id/{token}/punches` (exige IP público/roteamento
     até o servidor — raramente disponível em rede de hotel pequeno).
  2. **Agente local (o que estamos construindo)**: o agente Go, na mesma rede do relógio,
     faz *polling* via API REST local do equipamento e repassa as batidas para o mesmo
     endpoint de webhook — não exige abrir porta nem mudar a rede do cliente.

### Protocolo REST local do Control iD (usado pelo agente)

Porta 80 (HTTP) do próprio equipamento, sessão por cookie:

```
POST /login.fcgi          {"login": "admin", "password": "..."}   → cookie de sessão
POST /load_objects.fcgi    {"object": "user"}                       → lista de usuários/matrículas
POST /get_catalog.fcgi     {"catalog": "access_logs", "id": <last_id ou 0>}
                                                                     → eventos de acesso/biometria
                                                                        (user_id, time, event, portal_id...)
POST /destroy_session.fcgi                                          → encerra sessão
```

Mapeamento de evento do Control iD → payload do webhook do Registro:

| Campo Control iD | Campo Registro |
|---|---|
| `user_id` (resolvido para matrícula/PIS via `load_objects` de `user`) | `external_id` |
| `time` (epoch) | `punched_at` |
| `event` (0/1 = entrada/saída, varia por modelo) | `type` (`"in"`/`"out"`) |
| `id` do log (contador incremental do equipamento) | `event_id` (garante idempotência via `uq_time_punches_device_event`) |

> **Observação**: o payload exato varia por firmware/modelo Control iD. O agente deve
> persistir o payload bruto (assim como o webhook já persiste `raw_payload`) e logar
> eventos não reconhecidos para ajuste fino sem perda de dados.

### Próximos protocolos a suportar (fora do escopo desta primeira entrega)

- **ZKTeco (protocolo `zklib`/porta 4370)**: exige um cliente binário próprio (biblioteca
  Go como `github.com/zkteco/zklib`-equivalente ainda não é 1st-party — precisa ser escrita
  ou portada de `pyzk`).
- **Parser de arquivo AFD** (Henry, Topdata, Madis): formato de arquivo-texto fixo, mais
  simples de implementar que protocolo de rede — bom candidato a segunda prioridade porque
  cobre 3 marcas de uma vez com um único parser.

## Domínio já existente no backend (referência)

- `api/app/domain/timeclock/` — routers, service, schemas.
- Model `TimeClockDevice` (`api/app/models/operations.py:823`) — `webhook_token` único por
  dispositivo, gerado com `secrets.token_hex(24)`.
- Endpoint de ingestão: `POST /integrations/control-id/{webhook_token}/punches`
  (`api/app/domain/timeclock/webhook_router.py`) — tolerante a nomes de campo alternativos,
  já persiste `raw_payload`, já deduplica por `event_id`.
- Fluxo de negócio completo (cálculo de atraso/status) documentado em
  [docs/integracao-escala-ponto.md](integracao-escala-ponto.md).
