// Command agent é o agente local que faz a ponte entre um relógio de ponto
// Control iD na rede da recepção e o backend do Registro na nuvem.
package main

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"sync/atomic"
	"syscall"

	"github.com/icarosimoes/registro-timeclock-agent/internal/config"
	syncpkg "github.com/icarosimoes/registro-timeclock-agent/internal/sync"
	"github.com/icarosimoes/registro-timeclock-agent/internal/tray"
	"github.com/icarosimoes/registro-timeclock-agent/internal/webui"
)

func main() {
	logger := slog.New(slog.NewTextHandler(os.Stdout, nil))
	slog.SetDefault(logger)

	cfg, err := config.Load()
	if err != nil {
		logger.Error("config_load_failed", "error", err)
		os.Exit(1)
	}
	dir, err := config.Dir()
	if err != nil {
		logger.Error("config_dir_failed", "error", err)
		os.Exit(1)
	}
	logger.Info("agent_starting", "config_dir", dir)

	store := config.NewStore(cfg)

	ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
	defer stop()

	syncer := syncpkg.New(store, dir, logger)
	ui := webui.New(store, syncer, logger)

	var shuttingDown atomic.Bool

	webUIAddr := cfg.WebUIAddr
	if webUIAddr == "" {
		webUIAddr = config.DefaultWebUIAddr
	}

	go func() {
		if err := ui.ListenAndServe(ctx, webUIAddr); err != nil {
			logger.Error("webui_listen_failed", "error", err, "addr", webUIAddr)
		}
	}()

	go syncer.Run(ctx)

	tray.Start(ctx, tray.Config{
		ConfigURL: fmt.Sprintf("http://%s/", webUIAddr),
		OnSyncNow: syncer.SyncNow,
		OnQuit: func() {
			if shuttingDown.CompareAndSwap(false, true) {
				stop()
			}
		},
	})

	logger.Info("agent_ready", "webui_addr", webUIAddr)

	<-ctx.Done()
	logger.Info("agent_shutting_down")
	// O logout do Control iD e o flush da fila pendente já acontecem a cada
	// ciclo de sync (internal/sync); não há estado de sessão vivo para
	// limpar aqui além do que os defers de syncer.Run/webui.ListenAndServe
	// já tratam ao observar ctx.Done().
}
