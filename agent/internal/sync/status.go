package sync

import (
	"sync"
	"time"
)

// Status é o estado observável do sync loop, lido pelo webui para mostrar a
// tela de status. Protegido por mutex porque é escrito pela goroutine do
// loop e lido pela goroutine HTTP do webui concorrentemente.
type Status struct {
	mu             sync.RWMutex
	lastSyncAt     time.Time
	lastSyncOK     bool
	lastError      string
	pendingCount   int
	lastEventCount int
}

type StatusSnapshot struct {
	LastSyncAt     time.Time
	LastSyncOK     bool
	LastError      string
	PendingCount   int
	LastEventCount int
}

func (s *Status) Snapshot() StatusSnapshot {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return StatusSnapshot{
		LastSyncAt:     s.lastSyncAt,
		LastSyncOK:     s.lastSyncOK,
		LastError:      s.lastError,
		PendingCount:   s.pendingCount,
		LastEventCount: s.lastEventCount,
	}
}

func (s *Status) recordSuccess(eventCount, pendingCount int) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.lastSyncAt = time.Now()
	s.lastSyncOK = true
	s.lastError = ""
	s.lastEventCount = eventCount
	s.pendingCount = pendingCount
}

func (s *Status) recordError(err error, pendingCount int) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.lastSyncAt = time.Now()
	s.lastSyncOK = false
	s.lastError = err.Error()
	s.pendingCount = pendingCount
}

func (s *Status) setPendingCount(n int) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.pendingCount = n
}
