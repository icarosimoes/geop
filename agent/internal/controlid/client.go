// Package controlid implementa um cliente mínimo para a API REST local do
// relógio de ponto/controle de acesso Control iD (porta 80, sessão via
// cookie). O contrato exato dos endpoints (`load_objects.fcgi`,
// `get_catalog.fcgi`) é documentado publicamente pelo fabricante, mas o
// formato de resposta varia por firmware/modelo — por isso o parsing é
// tolerante (campos desconhecidos vão para RawFields) e não há testes de
// integração aqui, só os testes de payload puro em internal/sync.
package controlid

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

const requestTimeout = 5 * time.Second

// Session guarda o cookie de sessão retornado pelo login e a base URL usada
// para montar as próximas chamadas.
type Session struct {
	BaseURL string
	Cookie  string
	client  *http.Client
}

// User é um usuário cadastrado no relógio. Registration é a matrícula/PIS que
// vira external_id no payload do webhook. Extra guarda qualquer campo que o
// firmware retorne além dos conhecidos, para não perder informação em caso de
// divergência de formato.
type User struct {
	ID           int            `json:"id"`
	Registration string         `json:"registration"`
	Name         string         `json:"name,omitempty"`
	Extra        map[string]any `json:"-"`
}

// AccessLog é um evento bruto de acesso/biometria retornado por
// get_catalog.fcgi. Time é epoch (segundos). Event é o código bruto do
// firmware (0/1 = entrada/saída na maioria dos modelos testados
// publicamente, mas isso é uma suposição documentada — não validada contra
// hardware real; ver EventToPunchType).
type AccessLog struct {
	ID     int   `json:"id"`
	UserID int   `json:"user_id"`
	Time   int64 `json:"time"`
	Event  int   `json:"event"`
}

// EventToPunchType mapeia o código bruto do relógio para "in"/"out". Essa
// tabela é uma suposição baseada na documentação pública do fabricante
// (evento 0 = entrada, 1 = saída em parte dos modelos; outros modelos usam
// 2/3 para uma segunda entrada/saída do dia). Ajuste aqui quando validar
// contra um equipamento real — mantido em uma função isolada e testável de
// propósito.
func EventToPunchType(event int) string {
	switch event {
	case 0, 2:
		return "in"
	case 1, 3:
		return "out"
	default:
		return ""
	}
}

func newClient() *http.Client {
	return &http.Client{Timeout: requestTimeout}
}

func postJSON(ctx context.Context, client *http.Client, url string, cookie string, body any, out any) (*http.Response, error) {
	buf, err := json.Marshal(body)
	if err != nil {
		return nil, fmt.Errorf("controlid: encoding request: %w", err)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(buf))
	if err != nil {
		return nil, fmt.Errorf("controlid: building request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")
	if cookie != "" {
		req.Header.Set("Cookie", cookie)
	}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("controlid: request failed: %w", err)
	}
	defer resp.Body.Close()

	data, err := io.ReadAll(resp.Body)
	if err != nil {
		return resp, fmt.Errorf("controlid: reading response: %w", err)
	}
	if resp.StatusCode >= 300 {
		return resp, fmt.Errorf("controlid: unexpected status %d: %s", resp.StatusCode, string(data))
	}
	if out != nil && len(bytes.TrimSpace(data)) > 0 {
		if err := json.Unmarshal(data, out); err != nil {
			return resp, fmt.Errorf("controlid: decoding response: %w", err)
		}
	}
	return resp, nil
}

// Login autentica no relógio e retorna uma Session com o cookie capturado do
// header Set-Cookie da resposta.
func Login(ctx context.Context, baseURL, user, password string) (*Session, error) {
	client := newClient()
	body := map[string]string{"login": user, "password": password}

	buf, err := json.Marshal(body)
	if err != nil {
		return nil, fmt.Errorf("controlid: encoding login: %w", err)
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, strings.TrimRight(baseURL, "/")+"/login.fcgi", bytes.NewReader(buf))
	if err != nil {
		return nil, fmt.Errorf("controlid: building login request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("controlid: login failed: %w", err)
	}
	defer resp.Body.Close()
	data, _ := io.ReadAll(resp.Body)
	if resp.StatusCode >= 300 {
		return nil, fmt.Errorf("controlid: login unexpected status %d: %s", resp.StatusCode, string(data))
	}

	var cookies []string
	for _, c := range resp.Cookies() {
		cookies = append(cookies, c.String())
	}
	// Alguns firmwares retornam a sessão no corpo em vez de Set-Cookie.
	if len(cookies) == 0 {
		var sessionBody struct {
			Session string `json:"session"`
		}
		if err := json.Unmarshal(data, &sessionBody); err == nil && sessionBody.Session != "" {
			cookies = append(cookies, "session="+sessionBody.Session)
		}
	}

	return &Session{
		BaseURL: strings.TrimRight(baseURL, "/"),
		Cookie:  strings.Join(cookies, "; "),
		client:  client,
	}, nil
}

// LoadUsers busca a lista de usuários cadastrados no relógio, usada para
// resolver UserID -> matrícula (external_id) dos logs de acesso.
func (s *Session) LoadUsers(ctx context.Context) ([]User, error) {
	var raw struct {
		User []map[string]any `json:"user"`
	}
	_, err := postJSON(ctx, s.client, s.BaseURL+"/load_objects.fcgi", s.Cookie, map[string]string{"object": "user"}, &raw)
	if err != nil {
		return nil, err
	}

	users := make([]User, 0, len(raw.User))
	for _, m := range raw.User {
		u := User{Extra: map[string]any{}}
		if id, ok := numericField(m, "id"); ok {
			u.ID = int(id)
		}
		if reg, ok := m["registration"].(string); ok {
			u.Registration = reg
		}
		if name, ok := m["name"].(string); ok {
			u.Name = name
		}
		for k, v := range m {
			if k != "id" && k != "registration" && k != "name" {
				u.Extra[k] = v
			}
		}
		users = append(users, u)
	}
	return users, nil
}

// GetAccessLogs busca eventos de acesso a partir de sinceID (exclusive).
//
// Suposição não validada contra hardware real: assumimos que get_catalog.fcgi
// aceita `{"catalog": "access_logs", "id": sinceID}` e retorna apenas os
// registros com ID maior que sinceID (paginação incremental por cursor). A
// documentação pública do fabricante não detalha esse contrato com precisão;
// se o firmware real retornar sempre a lista completa, o filtro por sinceID
// abaixo (ainda) garante que só processamos eventos novos.
func (s *Session) GetAccessLogs(ctx context.Context, sinceID int) ([]AccessLog, error) {
	var raw struct {
		AccessLogs []map[string]any `json:"access_logs"`
	}
	body := map[string]any{"catalog": "access_logs", "id": sinceID}
	_, err := postJSON(ctx, s.client, s.BaseURL+"/get_catalog.fcgi", s.Cookie, body, &raw)
	if err != nil {
		return nil, err
	}

	logs := make([]AccessLog, 0, len(raw.AccessLogs))
	for _, m := range raw.AccessLogs {
		var l AccessLog
		if id, ok := numericField(m, "id"); ok {
			l.ID = int(id)
		}
		if uid, ok := numericField(m, "user_id"); ok {
			l.UserID = int(uid)
		}
		if t, ok := numericField(m, "time"); ok {
			l.Time = int64(t)
		}
		if ev, ok := numericField(m, "event"); ok {
			l.Event = int(ev)
		}
		if l.ID > sinceID {
			logs = append(logs, l)
		}
	}
	return logs, nil
}

// Logout encerra a sessão no equipamento. Erros aqui são não-fatais (a
// sessão expira sozinha do lado do relógio).
func (s *Session) Logout(ctx context.Context) error {
	_, err := postJSON(ctx, s.client, s.BaseURL+"/destroy_session.fcgi", s.Cookie, map[string]string{}, nil)
	return err
}

func numericField(m map[string]any, key string) (float64, bool) {
	v, ok := m[key]
	if !ok {
		return 0, false
	}
	switch n := v.(type) {
	case float64:
		return n, true
	case int:
		return float64(n), true
	case string:
		var f float64
		if _, err := fmt.Sscanf(n, "%f", &f); err == nil {
			return f, true
		}
	}
	return 0, false
}
