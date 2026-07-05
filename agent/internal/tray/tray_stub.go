//go:build !systray

package tray

import (
	"context"
	"log/slog"
)

// Start roda em modo headless: não há ícone de bandeja nesta build (compilada
// sem a tag `systray`), então só logamos um aviso uma vez. O agente continua
// funcionando normalmente via webui + sync — a bandeja é um complemento, não
// um requisito.
func Start(ctx context.Context, cfg Config) {
	slog.Warn(
		"tray_unavailable_running_headless",
		"reason", "build sem a tag 'systray' (evita dependência de cgo/libayatana-appindicator)",
		"config_url", cfg.ConfigURL,
	)
}
