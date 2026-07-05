# Agente de Ponto Registro (Control iD)

Agente local, em Go puro, que roda no computador da recepção do hotel,
conversa com um relógio de ponto Control iD na rede local e repassa as
batidas para o backend do Registro via
`POST /integrations/control-id/{webhook_token}/punches`
(`api/app/domain/timeclock/webhook_router.py`).

É o equivalente, para ponto biométrico, do que um agente tipo "Kairos" é para
PDV: um processo que roda perto do hardware e faz a ponte para a nuvem, sem
exigir que o equipamento tenha rota direta até a internet.

## Como compilar

Requer Go 1.22+.

```bash
cd agent
go build -o bin/registro-agent ./cmd/agent
```

Isso gera um binário headless (sem ícone de bandeja) — ver seção "Bandeja do
sistema" abaixo.

## Como rodar

```bash
./bin/registro-agent
```

ou, em desenvolvimento:

```bash
go run ./cmd/agent
```

Na primeira execução, o agente sobe com uma configuração vazia. Acesse
**http://127.0.0.1:47334/** no navegador para configurar:

- **URL base do Registro**: ex. `https://minhaempresa.registro.app` (produção)
  ou `http://localhost:8000` (dev local).
- **Webhook token**: crie o relógio (`TimeClockDevice`) no painel web do
  Registro primeiro — o cadastro gera um `webhook_token` único. Copie esse
  token para cá.
- **Host/IP, usuário e senha do relógio Control iD** na rede local.
- **Intervalo de polling** (padrão: 30s).

Salvar a configuração já reinicia o loop de sincronização com os novos
valores, sem precisar reiniciar o processo.

Use o botão **"Sincronizar agora"** (ou o item de mesmo nome no menu da
bandeja) para forçar um ciclo imediato, útil para depurar a conexão com o
relógio ou com o backend.

## Onde fica o config.json

`os.UserConfigDir()/registro-timeclock-agent/config.json`

Em Linux, isso normalmente é `~/.config/registro-timeclock-agent/config.json`.
No mesmo diretório ficam também:

- `last_sync.json` — cursor do último evento de acesso já lido do relógio
  (evita reprocessar tudo a cada reinício; reprocessar seria seguro mesmo
  assim, porque o webhook do backend deduplica por `event_id`).
- `pending_events.json` — fila de eventos que falharam ao ser enviados ao
  backend (rede fora, servidor indisponível) e serão reenviados no próximo
  ciclo, antes de buscar eventos novos.

A senha do relógio é gravada em texto puro no `config.json`. Isso é uma
decisão consciente, não um descuido: é a senha de um equipamento de rede
local (não uma credencial de nuvem), o arquivo herda as permissões do
diretório de config do usuário do SO (`0600`), e adicionar criptografia
exigiria gerenciar uma chave em outro lugar sem reduzir de fato o risco para
essa ameaça específica (acesso físico/root à própria máquina da recepção).

## UI local de configuração

Serve em `127.0.0.1:47334` por padrão (loopback apenas). **Não tem
autenticação** — decisão consciente, na mesma linha de ferramentas como PDVs
locais ou o painel de administração de um roteador doméstico: por estar em
loopback, só quem já tem acesso à própria máquina da recepção alcança essa
UI. Se um dia o agente precisar escutar em uma interface não-loopback, essa
decisão deve ser revisitada.

## Bandeja do sistema (systray)

O binário padrão (`go build ./...`, sem tags) roda **headless**: só webui +
loop de sync, sem ícone de bandeja. Isso é proposital — a biblioteca de
bandeja (`github.com/getlantern/systray`) depende, no Linux, de
`pkg-config` + GTK + `libayatana-appindicator` (dependências de sistema via
cgo) que nem sempre estão disponíveis (não estavam, por exemplo, na máquina
usada para desenvolver este agente).

Para habilitar a bandeja em uma máquina com essas dependências instaladas:

```bash
go build -tags systray -o bin/registro-agent ./cmd/agent
```

O menu da bandeja tem três itens: "Abrir configurações" (abre
`http://127.0.0.1:47334/` no navegador padrão), "Sincronizar agora" e "Sair".
O ícone é gerado em memória (`internal/icon`) — um quadrado 16x16 de cor
sólida via `image`+`image/png` da stdlib, sem nenhum asset no repositório.
No Windows, o mesmo PNG é empacotado dentro de um contêiner ICO mínimo
(ICONDIR + ICONDIRENTRY + dados PNG crus), truque suportado nativamente desde
o Vista.

Se a build com `-tags systray` não estiver disponível (ou a lib falhar em
runtime), o agente deve continuar funcionando normalmente via webui + sync —
a bandeja é um complemento, nunca um requisito para o funcionamento.

## Como funciona o loop de sincronização

A cada `PollIntervalSeconds`:

1. Tenta reenviar a fila de retry em disco (`pending_events.json`), se houver.
2. Faz login no relógio (`POST /login.fcgi`).
3. Renova o cache `user_id -> matrícula` a cada 5 minutos (não a cada ciclo).
4. Busca logs de acesso novos desde o cursor persistido
   (`GET/POST get_catalog.fcgi`).
5. Monta o payload `{"events": [{"external_id", "punched_at", "type",
   "event_id"}, ...]}` no formato aceito pelo webhook.
6. Envia via `POST {RegistroBaseURL}/integrations/control-id/{WebhookToken}/punches`.
7. Se o envio falhar, os eventos entram na fila de retry (não são perdidos).
8. Faz logout do relógio.

Reenviar o mesmo evento é seguro: o backend deduplica por `event_id`.

## Limitações conhecidas (payload não validado contra hardware real)

**Não há um relógio Control iD real disponível para validar este agente.**
As suposições abaixo replicam a mesma ressalva que já existe no backend
(`api/app/domain/timeclock/webhook_router.py`, ver docstring do módulo) e
estão documentadas em comentário no código-fonte, próximas de onde afetam o
comportamento:

- **Login** (`internal/controlid/client.go`, `Login`): assume que a sessão
  vem via cookie `Set-Cookie` padrão; alguns firmwares podem retornar a
  sessão no corpo da resposta em vez de cookie — há um fallback para esse
  caso, mas não testado contra equipamento real.
- **Paginação incremental dos logs** (`GetAccessLogs`): assume que
  `get_catalog.fcgi` com `{"catalog": "access_logs", "id": sinceID}` retorna
  (ou pode ser filtrado para) apenas os registros com ID maior que `sinceID`.
  Se o firmware real sempre retornar a lista completa, o filtro local por
  `sinceID` no código ainda garante que só processamos eventos novos.
- **Mapeamento de evento → tipo de batida** (`EventToPunchType`): assume
  `0`/`2` = entrada e `1`/`3` = saída, baseado na documentação pública do
  fabricante — varia por modelo/firmware. Isolado em uma função só para
  facilitar o ajuste quando houver hardware real para validar.
- **Campo de matrícula**: assume que `load_objects.fcgi` com
  `{"object": "user"}` retorna cada usuário com um campo `registration`
  igual à matrícula/PIS usada como `external_id`. Campos desconhecidos do
  firmware são capturados em `User.Extra` (`map[string]any`) para não perder
  informação.

Nenhuma dessas suposições tem teste de integração (não há como, sem
hardware). A lógica pura de montagem de payload (mapeamento in/out,
formatação de timestamp RFC3339, avanço de cursor, deduplicação por
`event_id`) tem testes unitários em `internal/sync/payload_test.go`.

## Estrutura

```
agent/
  cmd/agent/main.go       — entrypoint: config, webui, sync loop, tray, sinais
  internal/config/        — struct de config + load/save em JSON
  internal/controlid/      — cliente REST do Control iD (login, usuários, logs, logout)
  internal/sync/           — loop de polling, fila de retry, POST pro webhook
  internal/webui/          — servidor HTTP local com UI de configuração (html/template)
  internal/tray/           — ícone de bandeja (systray, opt-in via build tag)
  internal/icon/           — geração de ícone PNG/ICO em memória
```

## Verificação

```bash
cd agent
go build ./...       # build padrão, headless, sem dependências de sistema
go vet ./...
go test ./...
go run ./cmd/agent &  # sobe o agente; UI em http://127.0.0.1:47334/
```
