//go:build systray

package tray

import (
	"context"
	"log/slog"
	"os/exec"
	"runtime"

	"github.com/getlantern/systray"

	"github.com/icarosimoes/registro-timeclock-agent/internal/icon"
)

// Start sobe o ícone de bandeja real. Só compilada com `-tags systray`, em
// plataformas com as dependências de sistema necessárias (no Linux, GTK +
// libayatana-appindicator via cgo).
func Start(ctx context.Context, cfg Config) {
	go systray.Run(func() { onReady(ctx, cfg) }, func() {
		if cfg.OnQuit != nil {
			cfg.OnQuit()
		}
	})

	go func() {
		<-ctx.Done()
		systray.Quit()
	}()
}

func onReady(ctx context.Context, cfg Config) {
	iconData := icon.PNG()
	if runtime.GOOS == "windows" {
		if ico := icon.ICO(); len(ico) > 0 {
			iconData = ico
		}
	}
	systray.SetIcon(iconData)
	systray.SetTitle("Registro — Ponto")
	systray.SetTooltip("Agente de ponto Registro")

	mOpen := systray.AddMenuItem("Abrir configurações", "Abre a UI local de configuração")
	mSync := systray.AddMenuItem("Sincronizar agora", "Dispara um ciclo de sync imediato")
	systray.AddSeparator()
	mQuit := systray.AddMenuItem("Sair", "Encerra o agente")

	for {
		select {
		case <-ctx.Done():
			return
		case <-mOpen.ClickedCh:
			openBrowser(cfg.ConfigURL)
		case <-mSync.ClickedCh:
			if cfg.OnSyncNow != nil {
				cfg.OnSyncNow()
			}
		case <-mQuit.ClickedCh:
			systray.Quit()
			return
		}
	}
}

func openBrowser(url string) {
	var cmd *exec.Cmd
	switch runtime.GOOS {
	case "windows":
		cmd = exec.Command("rundll32", "url.dll,FileProtocolHandler", url)
	case "darwin":
		cmd = exec.Command("open", url)
	default:
		cmd = exec.Command("xdg-open", url)
	}
	if err := cmd.Start(); err != nil {
		slog.Warn("tray_open_browser_failed", "error", err, "url", url)
	}
}
