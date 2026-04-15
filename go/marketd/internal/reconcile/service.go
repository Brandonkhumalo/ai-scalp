package reconcile

import (
	"context"
	"log/slog"

	"github.com/shopspring/decimal"
	"github.com/tishanyq/ai-scalp/marketd/internal/alpaca"
	"github.com/tishanyq/ai-scalp/marketd/internal/store"
)

type Service struct {
	store      *store.Store
	alpaca     *alpaca.Client
	logger     *slog.Logger
	shadowMode bool
}

func NewService(store *store.Store, alpacaClient *alpaca.Client, logger *slog.Logger, shadowMode bool) *Service {
	return &Service{
		store:      store,
		alpaca:     alpacaClient,
		logger:     logger,
		shadowMode: shadowMode,
	}
}

func (s *Service) ReconcileUser(ctx context.Context, user store.User) (store.ReconciliationResult, error) {
	result := store.ReconciliationResult{}

	alpacaPositions, err := s.alpaca.GetPositions(ctx)
	if err != nil {
		return result, err
	}
	alpacaSymbols := make(map[string]struct{}, len(alpacaPositions))
	for _, p := range alpacaPositions {
		alpacaSymbols[p.Symbol] = struct{}{}
	}

	dbTrades, err := s.store.GetOpenStockTradesForUser(ctx, user.ID)
	if err != nil {
		return result, err
	}

	seen := map[string]struct{}{}
	for _, trade := range dbTrades {
		_, onAlpaca := alpacaSymbols[trade.Symbol]
		_, duplicate := seen[trade.Symbol]

		if !onAlpaca || duplicate {
			if s.shadowMode {
				s.logger.Info("shadow reconciliation action",
					"user", user.Email,
					"trade_id", trade.ID,
					"symbol", trade.Symbol,
					"action", actionFor(onAlpaca, duplicate),
				)
			} else {
				if !onAlpaca {
					if err := s.store.MarkTradeClosed(ctx, trade.ID, trade.EntryPrice, decimal.Zero); err != nil {
						s.logger.Error("failed to mark externally closed trade", "trade_id", trade.ID, "error", err)
					} else {
						result.PositionsClosed++
					}
				} else if duplicate {
					if err := s.store.DeleteTrade(ctx, trade.ID); err != nil {
						s.logger.Error("failed to delete duplicate trade", "trade_id", trade.ID, "error", err)
					} else {
						result.GhostsRemoved++
					}
				}
			}
		}
		seen[trade.Symbol] = struct{}{}
	}

	result.AlpacaPositions = len(alpacaPositions)
	result.DatabasePositions = len(dbTrades)
	result.PositionsSynced = len(dbTrades) - result.GhostsRemoved
	result.InSync = result.PositionsSynced == result.AlpacaPositions
	return result, nil
}

func actionFor(onAlpaca, duplicate bool) string {
	if !onAlpaca {
		return "mark_closed_or_delete_orphan"
	}
	if duplicate {
		return "delete_duplicate"
	}
	return "none"
}
