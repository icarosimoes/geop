// Package tray sobe (best-effort) um ícone na bandeja do sistema com um menu
// simples: abrir a UI de configuração, sincronizar agora, sair.
//
// A implementação real usa github.com/getlantern/systray, que no Linux
// depende de libayatana-appindicator/gtk via cgo (pacotes de sistema que nem
// sempre estão disponíveis — não estão neste ambiente de build, por
// exemplo). Para garantir que `go build ./...` sempre funcione mesmo sem
// essas dependências, a implementação real só é compilada com a build tag
// `systray` (`go build -tags systray ./...`); por padrão (sem a tag) o
// agente roda em modo headless (só webui + sync), logando um aviso — ver
// tray_stub.go.
package tray

// Config reúne os callbacks que o menu da bandeja aciona.
type Config struct {
	ConfigURL string
	OnSyncNow func()
	OnQuit    func()
}
