package app

import (
	"context"
	"encoding/json"
	"log/slog"
	"net/http"

	"github.com/tishanyq/ai-scalp/marketd/internal/config"
)

type statusResponse struct {
	Service      string `json:"service"`
	ShadowMode   bool   `json:"shadow_mode"`
	UseGoMarketD bool   `json:"use_go_marketd"`
	Status       string `json:"status"`
}

func startHTTPServer(ctx context.Context, cfg config.Config, logger *slog.Logger) *http.Server {
	mux := http.NewServeMux()
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(statusResponse{
			Service:      "marketd",
			ShadowMode:   cfg.ShadowMode,
			UseGoMarketD: cfg.UseGoMarketD,
			Status:       "ok",
		})
	})

	srv := &http.Server{Addr: cfg.ListenAddr, Handler: mux}
	go func() {
		<-ctx.Done()
		if err := srv.Shutdown(context.Background()); err != nil {
			logger.Warn("http shutdown failed", "error", err)
		}
	}()
	go func() {
		logger.Info("http control server listening", "addr", cfg.ListenAddr)
		if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			logger.Error("http server failed", "error", err)
		}
	}()
	return srv
}
