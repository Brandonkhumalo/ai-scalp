package config

import (
	"fmt"
	"os"
	"strconv"
	"time"
)

type Config struct {
	AppEnv                      string
	ShadowMode                  bool
	UseGoMarketD                bool
	LogLevel                    string
	DatabaseURL                 string
	AlpacaAPIKey                string
	AlpacaAPISecret             string
	AlpacaDataURL               string
	AlpacaTradingURL            string
	AlpacaRequestPerSecond      float64
	AlpacaRequestBurst          int
	ScalpingInterval            time.Duration
	ReconciliationInterval      time.Duration
	ScalpingProfitTargetPercent float64
	ScalpingStopLossPercent     float64
	MarketDataFeed              string
	ListenAddr                  string
}

func Load() (Config, error) {
	cfg := Config{
		AppEnv:                      getEnv("APP_ENV", "development"),
		ShadowMode:                  getBoolEnv("MARKETD_SHADOW_MODE", true),
		UseGoMarketD:                getBoolEnv("USE_GO_MARKETD", false),
		LogLevel:                    getEnv("MARKETD_LOG_LEVEL", "info"),
		DatabaseURL:                 os.Getenv("DATABASE_URL"),
		AlpacaAPIKey:                os.Getenv("ALPACA_API_KEY"),
		AlpacaAPISecret:             os.Getenv("ALPACA_API_SECRET"),
		AlpacaDataURL:               getEnv("ALPACA_DATA_URL", "https://data.alpaca.markets"),
		AlpacaTradingURL:            getEnv("ALPACA_TRADING_URL", "https://api.alpaca.markets"),
		AlpacaRequestPerSecond:      getFloatEnv("ALPACA_RPS", 8),
		AlpacaRequestBurst:          getIntEnv("ALPACA_BURST", 8),
		ScalpingInterval:            getDurationEnv("MARKETD_SCALPING_INTERVAL", 15*time.Second),
		ReconciliationInterval:      getDurationEnv("MARKETD_RECONCILIATION_INTERVAL", 2*time.Minute),
		ScalpingProfitTargetPercent: getFloatEnv("MARKETD_SCALPING_PROFIT_TARGET", 0.02),
		ScalpingStopLossPercent:     getFloatEnv("MARKETD_SCALPING_STOP_LOSS", 0.01),
		MarketDataFeed:              getEnv("MARKETD_MARKET_DATA_FEED", "iex"),
		ListenAddr:                  getEnv("MARKETD_LISTEN_ADDR", ":8090"),
	}

	if cfg.DatabaseURL == "" {
		return Config{}, fmt.Errorf("DATABASE_URL is required for marketd")
	}
	if cfg.AlpacaAPIKey == "" || cfg.AlpacaAPISecret == "" {
		return Config{}, fmt.Errorf("ALPACA_API_KEY and ALPACA_API_SECRET are required")
	}

	return cfg, nil
}

func getEnv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}

func getBoolEnv(key string, fallback bool) bool {
	if v := os.Getenv(key); v != "" {
		parsed, err := strconv.ParseBool(v)
		if err == nil {
			return parsed
		}
	}
	return fallback
}

func getFloatEnv(key string, fallback float64) float64 {
	if v := os.Getenv(key); v != "" {
		parsed, err := strconv.ParseFloat(v, 64)
		if err == nil {
			return parsed
		}
	}
	return fallback
}

func getIntEnv(key string, fallback int) int {
	if v := os.Getenv(key); v != "" {
		parsed, err := strconv.Atoi(v)
		if err == nil {
			return parsed
		}
	}
	return fallback
}

func getDurationEnv(key string, fallback time.Duration) time.Duration {
	if v := os.Getenv(key); v != "" {
		parsed, err := time.ParseDuration(v)
		if err == nil {
			return parsed
		}
	}
	return fallback
}
