package sync

import (
	"time"

	"github.com/icarosimoes/registro-timeclock-agent/internal/controlid"
)

// WebhookEvent é o formato exato aceito por
// POST /integrations/control-id/{webhook_token}/punches no backend do
// Registro (ver api/app/domain/timeclock/webhook_router.py:_parse_events).
type WebhookEvent struct {
	ExternalID string `json:"external_id"`
	PunchedAt  string `json:"punched_at"`
	Type       string `json:"type,omitempty"`
	EventID    string `json:"event_id"`
}

// WebhookPayload é o corpo do POST para o webhook.
type WebhookPayload struct {
	Events []WebhookEvent `json:"events"`
}

// BuildEvents converte uma lista de AccessLog do relógio em eventos no
// formato do webhook, usando userIDToExternalID para resolver a matrícula.
// Logs cujo UserID não está no mapa são ignorados (o usuário pode ter sido
// cadastrado depois do cache de usuários ter sido montado; o próximo ciclo,
// com cache renovado, processa esse log porque ele continua com ID maior que
// o sinceID persistido apenas depois de ser processado com sucesso).
//
// Função pura de propósito: não faz I/O, para ser testável sem hardware real.
func BuildEvents(logs []controlid.AccessLog, userIDToExternalID map[int]string) []WebhookEvent {
	events := make([]WebhookEvent, 0, len(logs))
	for _, l := range logs {
		externalID, ok := userIDToExternalID[l.UserID]
		if !ok || externalID == "" {
			continue
		}
		events = append(events, WebhookEvent{
			ExternalID: externalID,
			PunchedAt:  time.Unix(l.Time, 0).UTC().Format(time.RFC3339),
			Type:       controlid.EventToPunchType(l.Event),
			EventID:    deviceEventID(l.ID),
		})
	}
	return events
}

// deviceEventID monta um event_id estável e único por evento do relógio. O
// prefixo evita colisão caso o mesmo agente também processe outra fonte de
// eventos no futuro (ex: outro relógio na mesma rede).
func deviceEventID(logID int) string {
	return "controlid-" + itoa(logID)
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	neg := n < 0
	if neg {
		n = -n
	}
	var buf [20]byte
	i := len(buf)
	for n > 0 {
		i--
		buf[i] = byte('0' + n%10)
		n /= 10
	}
	if neg {
		i--
		buf[i] = '-'
	}
	return string(buf[i:])
}

// MaxLogID retorna o maior ID entre os logs, ou sinceID se a lista estiver
// vazia (nada avança o cursor).
func MaxLogID(logs []controlid.AccessLog, sinceID int) int {
	max := sinceID
	for _, l := range logs {
		if l.ID > max {
			max = l.ID
		}
	}
	return max
}
