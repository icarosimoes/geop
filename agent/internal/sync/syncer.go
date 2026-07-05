// Package sync implementa o loop de polling que busca batidas no relógio
// Control iD e as repassa para o webhook do backend do Registro, com fila de
// retry em disco para não perder eventos quando o backend está indisponível.
package sync

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"net/http"
	"strings"
	"time"

	"github.com/icarosimoes/registro-timeclock-agent/internal/config"
	"github.com/icarosimoes/registro-timeclock-agent/internal/controlid"
)

const (
	webhookTimeout = 10 * time.Second
	userCacheTTL   = 5 * time.Minute
)

// Syncer executa o loop de sync. Cada campo mutável é acessado só pela
// goroutine de Run, exceto Status (thread-safe por design) e o Store de
// config (também thread-safe).
type Syncer struct {
	store   *config.Store
	dir     string
	pending *PendingQueue
	status  *Status
	logger  *slog.Logger

	httpClient *http.Client
	triggerCh  chan struct{}

	userCache   map[int]string
	userCacheAt time.Time
}

func New(store *config.Store, dir string, logger *slog.Logger) *Syncer {
	if logger == nil {
		logger = slog.Default()
	}
	return &Syncer{
		store:      store,
		dir:        dir,
		pending:    NewPendingQueue(dir),
		status:     &Status{},
		logger:     logger,
		httpClient: &http.Client{Timeout: webhookTimeout},
		triggerCh:  make(chan struct{}, 1),
	}
}

func (s *Syncer) Status() StatusSnapshot {
	return s.status.Snapshot()
}

// SyncNow agenda um ciclo imediato, sem esperar o timer. Não bloqueia: se já
// houver um ciclo pendente na fila do canal, a chamada é ignorada (o próximo
// ciclo já vai rodar).
func (s *Syncer) SyncNow() {
	select {
	case s.triggerCh <- struct{}{}:
	default:
	}
}

// Run bloqueia até ctx ser cancelado, rodando um ciclo a cada
// PollIntervalSeconds (reconfigurável em tempo real via config.Store) ou
// imediatamente quando SyncNow é chamado.
func (s *Syncer) Run(ctx context.Context) {
	s.status.setPendingCount(s.pending.Count())

	cfgCh := s.store.Subscribe()
	interval := time.Duration(s.store.Get().PollIntervalSeconds) * time.Second
	if interval <= 0 {
		interval = time.Duration(config.DefaultPollIntervalSeconds) * time.Second
	}
	timer := time.NewTimer(interval)
	defer timer.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case cfg := <-cfgCh:
			newInterval := time.Duration(cfg.PollIntervalSeconds) * time.Second
			if newInterval <= 0 {
				newInterval = time.Duration(config.DefaultPollIntervalSeconds) * time.Second
			}
			if newInterval != interval {
				interval = newInterval
				if !timer.Stop() {
					<-timer.C
				}
				timer.Reset(interval)
			}
		case <-s.triggerCh:
			s.runCycle(ctx)
		case <-timer.C:
			s.runCycle(ctx)
			timer.Reset(interval)
		}
	}
}

func (s *Syncer) runCycle(ctx context.Context) {
	cfg := s.store.Get()
	if cfg.RegistroBaseURL == "" || cfg.WebhookToken == "" || cfg.ClockHost == "" {
		s.logger.Warn("sync_cycle_skipped_incomplete_config")
		return
	}

	s.flushPending(ctx, cfg)

	session, err := controlid.Login(ctx, "http://"+cfg.ClockHost, cfg.ClockUser, cfg.ClockPassword)
	if err != nil {
		s.logger.Error("controlid_login_failed", "error", err)
		s.status.recordError(fmt.Errorf("login no relógio: %w", err), s.pending.Count())
		return
	}
	defer func() {
		if err := session.Logout(ctx); err != nil {
			s.logger.Warn("controlid_logout_failed", "error", err)
		}
	}()

	if err := s.refreshUserCacheIfStale(ctx, session); err != nil {
		s.logger.Error("controlid_load_users_failed", "error", err)
		s.status.recordError(fmt.Errorf("carregar usuários do relógio: %w", err), s.pending.Count())
		return
	}

	sinceID, err := loadLastSyncID(s.dir)
	if err != nil {
		s.logger.Error("last_sync_load_failed", "error", err)
		sinceID = 0
	}

	logs, err := session.GetAccessLogs(ctx, sinceID)
	if err != nil {
		s.logger.Error("controlid_get_access_logs_failed", "error", err)
		s.status.recordError(fmt.Errorf("buscar batidas do relógio: %w", err), s.pending.Count())
		return
	}

	newMaxID := MaxLogID(logs, sinceID)
	if newMaxID != sinceID {
		if err := saveLastSyncID(s.dir, newMaxID); err != nil {
			s.logger.Error("last_sync_save_failed", "error", err)
		}
	}

	events := BuildEvents(logs, s.userCache)
	if len(events) == 0 {
		s.logger.Info("sync_cycle_no_new_events", "logs_fetched", len(logs))
		s.status.recordSuccess(0, s.pending.Count())
		return
	}

	if err := s.postEvents(ctx, cfg, events); err != nil {
		s.logger.Error("webhook_post_failed", "error", err, "event_count", len(events))
		pendingEvents, _ := s.pending.Load()
		pendingEvents = append(pendingEvents, events...)
		if saveErr := s.pending.Save(pendingEvents); saveErr != nil {
			s.logger.Error("pending_queue_save_failed", "error", saveErr)
		}
		s.status.recordError(err, len(pendingEvents))
		return
	}

	s.logger.Info("sync_cycle_success", "event_count", len(events))
	s.status.recordSuccess(len(events), s.pending.Count())
}

// flushPending tenta reenviar a fila de retry antes de buscar eventos novos,
// para respeitar a ordem de chegada dos eventos no backend. Falha aqui não
// interrompe o ciclo — a fila persiste em disco e será tentada de novo no
// próximo ciclo.
func (s *Syncer) flushPending(ctx context.Context, cfg config.Config) {
	events, err := s.pending.Load()
	if err != nil {
		s.logger.Error("pending_queue_load_failed", "error", err)
		return
	}
	if len(events) == 0 {
		return
	}
	if err := s.postEvents(ctx, cfg, events); err != nil {
		s.logger.Warn("pending_queue_flush_failed", "error", err, "pending_count", len(events))
		return
	}
	s.logger.Info("pending_queue_flushed", "event_count", len(events))
	if err := s.pending.Save(nil); err != nil {
		s.logger.Error("pending_queue_clear_failed", "error", err)
	}
}

func (s *Syncer) refreshUserCacheIfStale(ctx context.Context, session *controlid.Session) error {
	if s.userCache != nil && time.Since(s.userCacheAt) < userCacheTTL {
		return nil
	}
	users, err := session.LoadUsers(ctx)
	if err != nil {
		return err
	}
	cache := make(map[int]string, len(users))
	for _, u := range users {
		if u.Registration != "" {
			cache[u.ID] = u.Registration
		}
	}
	s.userCache = cache
	s.userCacheAt = time.Now()
	s.logger.Info("user_cache_refreshed", "user_count", len(cache))
	return nil
}

func (s *Syncer) postEvents(ctx context.Context, cfg config.Config, events []WebhookEvent) error {
	payload := WebhookPayload{Events: events}
	buf, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("encoding payload: %w", err)
	}

	url := strings.TrimRight(cfg.RegistroBaseURL, "/") + "/integrations/control-id/" + cfg.WebhookToken + "/punches"
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(buf))
	if err != nil {
		return fmt.Errorf("building request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := s.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 300 {
		return fmt.Errorf("webhook returned status %d", resp.StatusCode)
	}
	return nil
}
