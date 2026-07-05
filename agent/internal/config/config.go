// Package config carrega e persiste a configuração do agente em um arquivo
// JSON no diretório de configuração do usuário do sistema operacional.
package config

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"sync"
)

const (
	dirName  = "registro-timeclock-agent"
	fileName = "config.json"

	DefaultPollIntervalSeconds = 30
	DefaultWebUIAddr           = "127.0.0.1:47334"
)

// Config é a configuração editável pelo usuário via internal/webui.
//
// A senha do relógio (ClockPassword) é armazenada em texto puro de propósito:
// é a senha de um equipamento de rede local (não uma credencial de nuvem), o
// arquivo já herda as permissões do diretório de config do usuário do SO, e
// adicionar criptografia aqui exigiria gerenciar uma chave em algum outro
// lugar sem ganho real de segurança para essa ameaça específica.
type Config struct {
	RegistroBaseURL     string `json:"registro_base_url"`
	WebhookToken        string `json:"webhook_token"`
	ClockHost           string `json:"clock_host"`
	ClockUser           string `json:"clock_user"`
	ClockPassword       string `json:"clock_password"`
	PollIntervalSeconds int    `json:"poll_interval_seconds"`
	DeviceLabel         string `json:"device_label"`
	WebUIAddr           string `json:"webui_addr"`
}

// Default retorna uma configuração vazia com os defaults mínimos preenchidos,
// usada quando ainda não existe config.json (primeira execução).
func Default() Config {
	return Config{
		PollIntervalSeconds: DefaultPollIntervalSeconds,
		WebUIAddr:           DefaultWebUIAddr,
	}
}

// Dir retorna o diretório onde o config.json e o last_sync.json ficam,
// criando-o se ainda não existir.
func Dir() (string, error) {
	base, err := os.UserConfigDir()
	if err != nil {
		return "", err
	}
	dir := filepath.Join(base, dirName)
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return "", err
	}
	return dir, nil
}

// Path retorna o caminho completo do config.json.
func Path() (string, error) {
	dir, err := Dir()
	if err != nil {
		return "", err
	}
	return filepath.Join(dir, fileName), nil
}

// Load lê o config.json do disco. Se o arquivo não existir, retorna Default()
// sem erro (primeira execução do agente).
func Load() (Config, error) {
	path, err := Path()
	if err != nil {
		return Config{}, err
	}
	data, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return Default(), nil
	}
	if err != nil {
		return Config{}, err
	}
	cfg := Default()
	if err := json.Unmarshal(data, &cfg); err != nil {
		return Config{}, err
	}
	if cfg.PollIntervalSeconds <= 0 {
		cfg.PollIntervalSeconds = DefaultPollIntervalSeconds
	}
	if cfg.WebUIAddr == "" {
		cfg.WebUIAddr = DefaultWebUIAddr
	}
	return cfg, nil
}

// Save grava a configuração no config.json, sobrescrevendo o conteúdo atual.
func Save(cfg Config) error {
	path, err := Path()
	if err != nil {
		return err
	}
	data, err := json.MarshalIndent(cfg, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, data, 0o600)
}

// Store guarda a configuração corrente em memória e notifica assinantes
// quando ela muda (usado pelo pacote sync para recarregar sem reiniciar o
// processo, e pelo webui para ler o estado atual).
type Store struct {
	mu     sync.RWMutex
	cfg    Config
	subs   []chan Config
	subsMu sync.Mutex
}

func NewStore(initial Config) *Store {
	return &Store{cfg: initial}
}

func (s *Store) Get() Config {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.cfg
}

// Set atualiza a configuração em memória, persiste em disco e notifica todos
// os assinantes (não bloqueia se algum assinante não estiver lendo).
func (s *Store) Set(cfg Config) error {
	if err := Save(cfg); err != nil {
		return err
	}
	s.mu.Lock()
	s.cfg = cfg
	s.mu.Unlock()

	s.subsMu.Lock()
	defer s.subsMu.Unlock()
	for _, ch := range s.subs {
		select {
		case ch <- cfg:
		default:
		}
	}
	return nil
}

// Subscribe retorna um canal que recebe a config mais recente toda vez que
// ela é atualizada via Set. O canal tem buffer 1 (só interessa o valor mais
// recente, não o histórico de mudanças).
func (s *Store) Subscribe() <-chan Config {
	ch := make(chan Config, 1)
	s.subsMu.Lock()
	s.subs = append(s.subs, ch)
	s.subsMu.Unlock()
	return ch
}
