package app

import (
	"context"
	"errors"
	"log/slog"
	"sync"
	"time"

	"github.com/tishanyq/ai-scalp/marketd/internal/alpaca"
	"github.com/tishanyq/ai-scalp/marketd/internal/config"
	"github.com/tishanyq/ai-scalp/marketd/internal/marketdata"
	"github.com/tishanyq/ai-scalp/marketd/internal/markethours"
	"github.com/tishanyq/ai-scalp/marketd/internal/reconcile"
	"github.com/tishanyq/ai-scalp/marketd/internal/scalper"
	"github.com/tishanyq/ai-scalp/marketd/internal/store"
)

func Run(ctx context.Context, cfg config.Config, logger *slog.Logger) error {
	db, err := store.New(ctx, cfg.DatabaseURL)
	if err != nil {
		return err
	}
	defer db.Close()

	alpacaClient := alpaca.NewClient(alpaca.Config{
		APIKey:     cfg.AlpacaAPIKey,
		APISecret:  cfg.AlpacaAPISecret,
		DataURL:    cfg.AlpacaDataURL,
		TradingURL: cfg.AlpacaTradingURL,
		RPS:        cfg.AlpacaRequestPerSecond,
		Burst:      cfg.AlpacaRequestBurst,
	})
	marketHours := markethours.NewService()
	marketData := marketdata.NewService(alpacaClient, logger)
	scalperSvc := scalper.NewService(db, alpacaClient, marketData, logger, cfg.ShadowMode, cfg.ScalpingProfitTargetPercent, cfg.ScalpingStopLossPercent)
	reconcileSvc := reconcile.NewService(db, alpacaClient, logger, cfg.ShadowMode)
	httpServer := startHTTPServer(ctx, cfg, logger)
	defer httpServer.Close()

	logger.Info("marketd started",
		"shadow_mode", cfg.ShadowMode,
		"use_go_marketd", cfg.UseGoMarketD,
		"scalping_interval", cfg.ScalpingInterval.String(),
		"reconciliation_interval", cfg.ReconciliationInterval.String(),
	)

	var wg sync.WaitGroup
	errCh := make(chan error, 2)

	wg.Add(1)
	go func() {
		defer wg.Done()
		errCh <- runScalpingLoop(ctx, db, marketHours, scalperSvc, cfg.ScalpingInterval, logger)
	}()

	wg.Add(1)
	go func() {
		defer wg.Done()
		errCh <- runReconciliationLoop(ctx, db, marketHours, reconcileSvc, cfg.ReconciliationInterval, logger)
	}()

	var loopErr error
	select {
	case <-ctx.Done():
		loopErr = ctx.Err()
	case loopErr = <-errCh:
	}

	wg.Wait()
	if errors.Is(loopErr, context.Canceled) {
		return nil
	}
	return loopErr
}

func runScalpingLoop(ctx context.Context, db *store.Store, marketHours *markethours.Service, svc *scalper.Service, interval time.Duration, logger *slog.Logger) error {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		if marketHours.IsUSMarketOpen() {
			users, err := db.GetTradingUsers(ctx)
			if err != nil {
				logger.Error("failed to fetch trading users", "loop", "scalping", "error", err)
			} else {
				for _, user := range users {
					if err := svc.RunOnce(ctx, user); err != nil {
						logger.Error("scalping run failed", "user", user.Email, "error", err)
					}
				}
			}
		} else {
			logger.Debug("US market closed; skipping scalping cycle")
		}

		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-ticker.C:
		}
	}
}

func runReconciliationLoop(ctx context.Context, db *store.Store, marketHours *markethours.Service, svc *reconcile.Service, interval time.Duration, logger *slog.Logger) error {
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		if marketHours.IsUSMarketOpen() {
			users, err := db.GetTradingUsers(ctx)
			if err != nil {
				logger.Error("failed to fetch trading users", "loop", "reconciliation", "error", err)
			} else {
				for _, user := range users {
					res, runErr := svc.ReconcileUser(ctx, user)
					if runErr != nil {
						logger.Error("reconciliation failed", "user", user.Email, "error", runErr)
						continue
					}
					logger.Info("reconciliation complete",
						"user", user.Email,
						"in_sync", res.InSync,
						"db_positions", res.DatabasePositions,
						"alpaca_positions", res.AlpacaPositions,
					)
				}
			}
		} else {
			logger.Debug("US market closed; skipping reconciliation cycle")
		}

		select {
		case <-ctx.Done():
			return ctx.Err()
		case <-ticker.C:
		}
	}
}
