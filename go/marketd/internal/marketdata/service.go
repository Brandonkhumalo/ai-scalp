package marketdata

import (
	"context"
	"log/slog"
	"strings"
	"sync"
	"time"

	"github.com/tishanyq/ai-scalp/marketd/internal/alpaca"
)

type snapshotCacheEntry struct {
	snapshot *alpaca.Snapshot
	expires  time.Time
}

type Service struct {
	client               *alpaca.Client
	logger               *slog.Logger
	cacheTTL             time.Duration
	rateLimitCooldownTil time.Time
	mu                   sync.RWMutex
	cache                map[string]snapshotCacheEntry
}

func NewService(client *alpaca.Client, logger *slog.Logger) *Service {
	return &Service{
		client:   client,
		logger:   logger,
		cacheTTL: 60 * time.Second,
		cache:    make(map[string]snapshotCacheEntry),
	}
}

func (s *Service) GetRealtimeSnapshot(ctx context.Context, symbol string) *alpaca.Snapshot {
	if symbol == "" {
		return nil
	}

	s.mu.RLock()
	entry, ok := s.cache[symbol]
	cooldown := time.Now().Before(s.rateLimitCooldownTil)
	s.mu.RUnlock()

	if ok && time.Now().Before(entry.expires) {
		return entry.snapshot
	}
	if cooldown {
		s.logger.Warn("market data cooldown active, using stale-or-empty cache", "symbol", symbol)
		if ok {
			return entry.snapshot
		}
		return nil
	}

	snap, err := s.client.GetSnapshot(ctx, symbol)
	if err != nil {
		s.logger.Warn("snapshot request failed", "symbol", symbol, "error", err)
		if contains429(err.Error()) {
			s.mu.Lock()
			s.rateLimitCooldownTil = time.Now().Add(15 * time.Second)
			s.mu.Unlock()
		}
		if ok {
			return entry.snapshot
		}
		return nil
	}

	s.mu.Lock()
	s.cache[symbol] = snapshotCacheEntry{snapshot: snap, expires: time.Now().Add(s.cacheTTL)}
	s.mu.Unlock()

	return snap
}

func contains429(v string) bool {
	return strings.Contains(v, "429")
}
