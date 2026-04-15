package markethours

import (
	"testing"
	"time"
)

func TestIsUSMarketOpen(t *testing.T) {
	svc := NewService()
	loc, err := time.LoadLocation("America/New_York")
	if err != nil {
		t.Fatalf("load location: %v", err)
	}
	svc.nowFn = func() time.Time {
		return time.Date(2026, 4, 14, 10, 0, 0, 0, loc)
	}

	if !svc.IsUSMarketOpen() {
		t.Fatalf("expected market to be open")
	}
}

func TestIsUSMarketClosedWeekend(t *testing.T) {
	svc := NewService()
	loc, err := time.LoadLocation("America/New_York")
	if err != nil {
		t.Fatalf("load location: %v", err)
	}
	svc.nowFn = func() time.Time {
		return time.Date(2026, 4, 12, 10, 0, 0, 0, loc)
	}

	if svc.IsUSMarketOpen() {
		t.Fatalf("expected market to be closed on Sunday")
	}
}
