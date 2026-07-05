package sync

import (
	"encoding/json"
	"errors"
	"os"
	"path/filepath"
	"sync"
)

const (
	lastSyncFileName = "last_sync.json"
	pendingFileName  = "pending_events.json"
)

// lastSyncState persiste o cursor incremental dos logs de acesso já
// processados, para que um reinício do agente não reprocesse tudo desde o
// início (reprocessar é seguro por causa da dedup por event_id no servidor,
// mas é desnecessário e mais lento).
type lastSyncState struct {
	LastLogID int `json:"last_log_id"`
}

func loadLastSyncID(dir string) (int, error) {
	path := filepath.Join(dir, lastSyncFileName)
	data, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return 0, nil
	}
	if err != nil {
		return 0, err
	}
	var s lastSyncState
	if err := json.Unmarshal(data, &s); err != nil {
		return 0, err
	}
	return s.LastLogID, nil
}

func saveLastSyncID(dir string, id int) error {
	path := filepath.Join(dir, lastSyncFileName)
	data, err := json.MarshalIndent(lastSyncState{LastLogID: id}, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, data, 0o600)
}

// PendingQueue é uma fila de eventos que falharam ao ser enviados ao webhook,
// persistida em disco para sobreviver a reinícios do agente. Protegida por
// mutex porque é lida/escrita tanto pelo loop de sync quanto (indiretamente,
// via Status) pelo webui.
type PendingQueue struct {
	mu   sync.Mutex
	dir  string
	path string
}

func NewPendingQueue(dir string) *PendingQueue {
	return &PendingQueue{dir: dir, path: filepath.Join(dir, pendingFileName)}
}

func (q *PendingQueue) Load() ([]WebhookEvent, error) {
	q.mu.Lock()
	defer q.mu.Unlock()
	data, err := os.ReadFile(q.path)
	if errors.Is(err, os.ErrNotExist) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	var events []WebhookEvent
	if err := json.Unmarshal(data, &events); err != nil {
		return nil, err
	}
	return events, nil
}

func (q *PendingQueue) Save(events []WebhookEvent) error {
	q.mu.Lock()
	defer q.mu.Unlock()
	if len(events) == 0 {
		if err := os.Remove(q.path); err != nil && !errors.Is(err, os.ErrNotExist) {
			return err
		}
		return nil
	}
	data, err := json.MarshalIndent(events, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(q.path, data, 0o600)
}

func (q *PendingQueue) Count() int {
	events, err := q.Load()
	if err != nil {
		return 0
	}
	return len(events)
}
