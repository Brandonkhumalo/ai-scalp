package scalper

import (
	"context"
	"fmt"
	"log/slog"
	"strings"
	"time"

	"github.com/shopspring/decimal"
	"github.com/tishanyq/ai-scalp/marketd/internal/alpaca"
	"github.com/tishanyq/ai-scalp/marketd/internal/marketdata"
	"github.com/tishanyq/ai-scalp/marketd/internal/store"
)

type Service struct {
	store        *store.Store
	alpacaClient *alpaca.Client
	marketData   *marketdata.Service
	logger       *slog.Logger
	profitTarget decimal.Decimal
	stopLoss     decimal.Decimal
	shadowMode   bool
}

type CloseCandidate struct {
	Trade        store.Trade
	CurrentPrice decimal.Decimal
	PnL          decimal.Decimal
	PctChange    decimal.Decimal
	Reason       string
}

func NewService(store *store.Store, alpacaClient *alpaca.Client, marketData *marketdata.Service, logger *slog.Logger, shadowMode bool, profitTarget, stopLoss float64) *Service {
	return &Service{
		store:        store,
		alpacaClient: alpacaClient,
		marketData:   marketData,
		logger:       logger,
		profitTarget: decimal.NewFromFloat(profitTarget),
		stopLoss:     decimal.NewFromFloat(stopLoss),
		shadowMode:   shadowMode,
	}
}

func (s *Service) RunOnce(ctx context.Context, user store.User) error {
	trades, err := s.store.GetOpenStockTradesForUser(ctx, user.ID)
	if err != nil {
		return err
	}
	if len(trades) == 0 {
		return nil
	}

	positions, err := s.alpacaClient.GetPositions(ctx)
	if err != nil {
		s.logger.Warn("failed to load alpaca positions for fallback pricing", "user", user.Email, "error", err)
	}
	priceFallback := map[string]decimal.Decimal{}
	for _, p := range positions {
		v, parseErr := decimal.NewFromString(p.CurrentPrice)
		if parseErr == nil {
			priceFallback[p.Symbol] = v
		}
	}

	var toClose []CloseCandidate
	for _, trade := range trades {
		currentPrice, ok := s.resolveCurrentPrice(ctx, trade.Symbol, priceFallback)
		if !ok {
			continue
		}

		qty := trade.Quantity
		entry := trade.EntryPrice

		var pnl decimal.Decimal
		var pct decimal.Decimal
		if strings.EqualFold(trade.Side, "buy") {
			pnl = currentPrice.Sub(entry).Mul(qty)
			pct = currentPrice.Sub(entry).Div(entry)
		} else {
			pnl = entry.Sub(currentPrice).Mul(qty)
			pct = entry.Sub(currentPrice).Div(entry)
		}

		reason := ""
		if pct.GreaterThanOrEqual(s.profitTarget) {
			reason = fmt.Sprintf("Profit Target (%s%%)", pct.Mul(decimal.NewFromInt(100)).StringFixed(2))
		} else if pct.LessThanOrEqual(s.stopLoss.Neg()) {
			reason = fmt.Sprintf("Stop Loss (%s%%)", pct.Mul(decimal.NewFromInt(100)).StringFixed(2))
		}
		if reason == "" {
			continue
		}
		toClose = append(toClose, CloseCandidate{Trade: trade, CurrentPrice: currentPrice, PnL: pnl, PctChange: pct, Reason: reason})
	}

	for _, candidate := range toClose {
		if s.shadowMode {
			s.logger.Info("shadow close candidate",
				"user", user.Email,
				"trade_id", candidate.Trade.ID,
				"symbol", candidate.Trade.Symbol,
				"reason", candidate.Reason,
				"pnl", candidate.PnL.StringFixed(2),
				"pct", candidate.PctChange.Mul(decimal.NewFromInt(100)).StringFixed(2),
			)
			continue
		}

		closeResult, err := s.alpacaClient.ClosePosition(ctx, candidate.Trade.Symbol)
		if err != nil {
			s.logger.Error("failed to close position", "symbol", candidate.Trade.Symbol, "trade_id", candidate.Trade.ID, "error", err)
			continue
		}
		if closeResult != nil {
			s.logger.Info("close order submitted", "symbol", candidate.Trade.Symbol, "order_id", closeResult.ID, "status", closeResult.Status)
		}

		verified, err := s.alpacaClient.VerifyPositionClosed(ctx, candidate.Trade.Symbol, 3, 1*time.Second)
		if err != nil {
			s.logger.Error("verification failed", "symbol", candidate.Trade.Symbol, "error", err)
			continue
		}
		if !verified {
			s.logger.Warn("position still open after close attempt", "symbol", candidate.Trade.Symbol)
			continue
		}

		if err := s.store.MarkTradeClosed(ctx, candidate.Trade.ID, candidate.CurrentPrice, candidate.PnL); err != nil {
			s.logger.Error("failed to mark trade closed", "trade_id", candidate.Trade.ID, "error", err)
			continue
		}
		reference := fmt.Sprintf("Trade #%d Auto-Closed (Scalping: %s)", candidate.Trade.ID, candidate.Reason)
		if err := s.store.CreateTradePNLTransaction(ctx, candidate.Trade.UserID, candidate.PnL, reference); err != nil {
			s.logger.Error("failed to create PnL transaction", "trade_id", candidate.Trade.ID, "error", err)
		}
	}

	return nil
}

func (s *Service) resolveCurrentPrice(ctx context.Context, symbol string, fallback map[string]decimal.Decimal) (decimal.Decimal, bool) {
	snapshot := s.marketData.GetRealtimeSnapshot(ctx, symbol)
	if snapshot != nil {
		if snapshot.LatestQuote.AskPrice > 0 {
			return decimal.NewFromFloat(snapshot.LatestQuote.AskPrice), true
		}
		if snapshot.LatestQuote.BidPrice > 0 {
			return decimal.NewFromFloat(snapshot.LatestQuote.BidPrice), true
		}
	}
	price, ok := fallback[symbol]
	return price, ok
}
