package sync

import (
	"testing"
	"time"

	"github.com/icarosimoes/registro-timeclock-agent/internal/controlid"
)

func TestBuildEvents_MapsInAndOutTypes(t *testing.T) {
	logs := []controlid.AccessLog{
		{ID: 1, UserID: 10, Time: 1720000000, Event: 0},
		{ID: 2, UserID: 10, Time: 1720003600, Event: 1},
	}
	users := map[int]string{10: "0001"}

	events := BuildEvents(logs, users)
	if len(events) != 2 {
		t.Fatalf("expected 2 events, got %d", len(events))
	}
	if events[0].Type != "in" {
		t.Errorf("expected first event type 'in', got %q", events[0].Type)
	}
	if events[1].Type != "out" {
		t.Errorf("expected second event type 'out', got %q", events[1].Type)
	}
	if events[0].ExternalID != "0001" {
		t.Errorf("expected external_id '0001', got %q", events[0].ExternalID)
	}
}

func TestBuildEvents_FormatsTimestampAsRFC3339(t *testing.T) {
	logs := []controlid.AccessLog{{ID: 1, UserID: 10, Time: 1720000000, Event: 0}}
	users := map[int]string{10: "0001"}

	events := BuildEvents(logs, users)
	if len(events) != 1 {
		t.Fatalf("expected 1 event, got %d", len(events))
	}
	want := time.Unix(1720000000, 0).UTC().Format(time.RFC3339)
	if events[0].PunchedAt != want {
		t.Errorf("expected punched_at %q, got %q", want, events[0].PunchedAt)
	}
	if _, err := time.Parse(time.RFC3339, events[0].PunchedAt); err != nil {
		t.Errorf("punched_at is not valid RFC3339: %v", err)
	}
}

func TestBuildEvents_SkipsUnknownUsers(t *testing.T) {
	logs := []controlid.AccessLog{
		{ID: 1, UserID: 10, Time: 1720000000, Event: 0},
		{ID: 2, UserID: 999, Time: 1720000001, Event: 0},
	}
	users := map[int]string{10: "0001"}

	events := BuildEvents(logs, users)
	if len(events) != 1 {
		t.Fatalf("expected 1 event (unknown user skipped), got %d", len(events))
	}
}

func TestBuildEvents_EventIDsAreUniquePerLog(t *testing.T) {
	logs := []controlid.AccessLog{
		{ID: 5, UserID: 10, Time: 1720000000, Event: 0},
		{ID: 6, UserID: 10, Time: 1720000001, Event: 1},
	}
	users := map[int]string{10: "0001"}

	events := BuildEvents(logs, users)
	if events[0].EventID == events[1].EventID {
		t.Errorf("expected distinct event_ids, got same value %q", events[0].EventID)
	}
	if events[0].EventID != "controlid-5" {
		t.Errorf("unexpected event_id format: %q", events[0].EventID)
	}
}

func TestMaxLogID_AdvancesCursor(t *testing.T) {
	logs := []controlid.AccessLog{{ID: 3}, {ID: 7}, {ID: 5}}
	if got := MaxLogID(logs, 1); got != 7 {
		t.Errorf("expected max id 7, got %d", got)
	}
}

func TestMaxLogID_KeepsSinceIDWhenNoLogs(t *testing.T) {
	if got := MaxLogID(nil, 42); got != 42 {
		t.Errorf("expected cursor to stay at 42 when no logs, got %d", got)
	}
}
