// Package webui serve a UI local de configuração do agente em
// 127.0.0.1:<porta configurável>. Não tem autenticação: é uma decisão
// consciente, documentada no README, alinhada com a postura de ferramentas
// como PDVs locais (Kairos) ou o painel de administração de um roteador
// doméstico — o servidor só escuta em loopback, então só quem já tem acesso
// à própria máquina da recepção consegue acessar.
package webui

import (
	"context"
	"html/template"
	"log/slog"
	"net/http"
	"time"

	"github.com/icarosimoes/registro-timeclock-agent/internal/config"
	"github.com/icarosimoes/registro-timeclock-agent/internal/sync"
)

const shutdownTimeout = 5 * time.Second

type Server struct {
	store  *config.Store
	syncer *sync.Syncer
	logger *slog.Logger
	tmpl   *template.Template
}

func New(store *config.Store, syncer *sync.Syncer, logger *slog.Logger) *Server {
	if logger == nil {
		logger = slog.Default()
	}
	return &Server{
		store:  store,
		syncer: syncer,
		logger: logger,
		tmpl:   template.Must(template.New("index").Parse(indexTemplate)),
	}
}

func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/", s.handleIndex)
	mux.HandleFunc("/save", s.handleSave)
	mux.HandleFunc("/sync-now", s.handleSyncNow)
	return mux
}

// ListenAndServe sobe o servidor HTTP local, bloqueando até ctx ser
// cancelado (o chamador deve rodar isso em uma goroutine).
func (s *Server) ListenAndServe(ctx context.Context, addr string) error {
	srv := &http.Server{Addr: addr, Handler: s.Handler()}
	go func() {
		<-ctx.Done()
		shutdownCtx, cancel := context.WithTimeout(context.Background(), shutdownTimeout)
		defer cancel()
		_ = srv.Shutdown(shutdownCtx)
	}()
	s.logger.Info("webui_listening", "addr", addr)
	err := srv.ListenAndServe()
	if err == http.ErrServerClosed {
		return nil
	}
	return err
}

type pageData struct {
	Config config.Config
	Status sync.StatusSnapshot
	Saved  bool
	Error  string
}

func (s *Server) handleIndex(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.NotFound(w, r)
		return
	}
	s.render(w, pageData{Config: s.store.Get(), Status: s.syncer.Status()})
}

func (s *Server) handleSave(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Redirect(w, r, "/", http.StatusSeeOther)
		return
	}
	if err := r.ParseForm(); err != nil {
		s.render(w, pageData{Config: s.store.Get(), Status: s.syncer.Status(), Error: "formulário inválido: " + err.Error()})
		return
	}

	cfg := s.store.Get()
	cfg.RegistroBaseURL = r.FormValue("registro_base_url")
	cfg.WebhookToken = r.FormValue("webhook_token")
	cfg.ClockHost = r.FormValue("clock_host")
	cfg.ClockUser = r.FormValue("clock_user")
	if pw := r.FormValue("clock_password"); pw != "" {
		cfg.ClockPassword = pw
	}
	cfg.DeviceLabel = r.FormValue("device_label")
	cfg.PollIntervalSeconds = parseIntOrDefault(r.FormValue("poll_interval_seconds"), cfg.PollIntervalSeconds)

	if err := s.store.Set(cfg); err != nil {
		s.render(w, pageData{Config: cfg, Status: s.syncer.Status(), Error: "erro ao salvar: " + err.Error()})
		return
	}
	s.render(w, pageData{Config: cfg, Status: s.syncer.Status(), Saved: true})
}

func (s *Server) handleSyncNow(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Redirect(w, r, "/", http.StatusSeeOther)
		return
	}
	s.syncer.SyncNow()
	http.Redirect(w, r, "/", http.StatusSeeOther)
}

func (s *Server) render(w http.ResponseWriter, data pageData) {
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	if err := s.tmpl.Execute(w, data); err != nil {
		s.logger.Error("template_render_failed", "error", err)
		http.Error(w, "erro interno ao renderizar página", http.StatusInternalServerError)
	}
}

func parseIntOrDefault(s string, def int) int {
	n := 0
	if s == "" {
		return def
	}
	for _, c := range s {
		if c < '0' || c > '9' {
			return def
		}
		n = n*10 + int(c-'0')
	}
	if n <= 0 {
		return def
	}
	return n
}

const indexTemplate = `
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<title>Registro — Agente de Ponto</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 640px; margin: 2rem auto; padding: 0 1rem; color: #1a1a1a; }
  h1 { font-size: 1.4rem; }
  fieldset { border: 1px solid #ccc; border-radius: 8px; margin-bottom: 1.5rem; padding: 1rem; }
  label { display: block; margin-top: 0.75rem; font-weight: 600; font-size: 0.9rem; }
  input { width: 100%; padding: 0.4rem; margin-top: 0.25rem; box-sizing: border-box; }
  button { margin-top: 1rem; padding: 0.5rem 1.2rem; cursor: pointer; }
  .status { background: #f5f5f5; border-radius: 8px; padding: 1rem; font-size: 0.9rem; }
  .ok { color: #1a7f37; }
  .err { color: #b91c1c; }
  .banner { padding: 0.6rem 1rem; border-radius: 6px; margin-bottom: 1rem; }
  .banner-ok { background: #dcfce7; color: #166534; }
  .banner-err { background: #fee2e2; color: #991b1b; }
</style>
</head>
<body>
<h1>Registro — Agente de Ponto (Control iD)</h1>

{{if .Saved}}<div class="banner banner-ok">Configuração salva.</div>{{end}}
{{if .Error}}<div class="banner banner-err">{{.Error}}</div>{{end}}

<div class="status">
  <strong>Status</strong><br>
  Último sync: {{if .Status.LastSyncAt.IsZero}}nunca{{else}}{{.Status.LastSyncAt.Format "02/01/2006 15:04:05"}}
    {{if .Status.LastSyncOK}}<span class="ok">(ok, {{.Status.LastEventCount}} evento(s))</span>{{else}}<span class="err">(falhou)</span>{{end}}
  {{end}}<br>
  Eventos pendentes na fila de retry: {{.Status.PendingCount}}<br>
  {{if .Status.LastError}}Último erro: <span class="err">{{.Status.LastError}}</span>{{end}}
</div>

<form method="post" action="/sync-now" style="margin-top:1rem;">
  <button type="submit">Sincronizar agora</button>
</form>

<form method="post" action="/save">
  <fieldset>
    <legend>Registro</legend>
    <label>URL base da API (ex: https://minhaempresa.registro.app)</label>
    <input type="text" name="registro_base_url" value="{{.Config.RegistroBaseURL}}" placeholder="http://localhost:8000">

    <label>Webhook token (criado no cadastro do relógio, no painel web do Registro)</label>
    <input type="text" name="webhook_token" value="{{.Config.WebhookToken}}">
  </fieldset>

  <fieldset>
    <legend>Relógio Control iD</legend>
    <label>Nome amigável (só exibição)</label>
    <input type="text" name="device_label" value="{{.Config.DeviceLabel}}" placeholder="Recepção">

    <label>Host/IP do relógio na rede local</label>
    <input type="text" name="clock_host" value="{{.Config.ClockHost}}" placeholder="192.168.0.50">

    <label>Usuário</label>
    <input type="text" name="clock_user" value="{{.Config.ClockUser}}" placeholder="admin">

    <label>Senha</label>
    <input type="password" name="clock_password" placeholder="(deixe em branco para manter a atual)">
  </fieldset>

  <fieldset>
    <legend>Sincronização</legend>
    <label>Intervalo de polling (segundos)</label>
    <input type="number" name="poll_interval_seconds" value="{{.Config.PollIntervalSeconds}}" min="5">
  </fieldset>

  <button type="submit">Salvar</button>
</form>

</body>
</html>
`
