package alpaca

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"

	"golang.org/x/time/rate"
)

type Config struct {
	APIKey     string
	APISecret  string
	DataURL    string
	TradingURL string
	RPS        float64
	Burst      int
}

type Client struct {
	httpClient *http.Client
	rateLimit  *rate.Limiter
	cfg        Config
}

type Position struct {
	Symbol       string `json:"symbol"`
	Qty          string `json:"qty"`
	CurrentPrice string `json:"current_price"`
}

type Snapshot struct {
	LatestQuote struct {
		AskPrice float64 `json:"ap"`
		BidPrice float64 `json:"bp"`
	} `json:"latestQuote"`
}

type ClosePositionResponse struct {
	ID     string `json:"id"`
	Status string `json:"status"`
}

func NewClient(cfg Config) *Client {
	return &Client{
		httpClient: &http.Client{Timeout: 15 * time.Second},
		rateLimit:  rate.NewLimiter(rate.Limit(cfg.RPS), cfg.Burst),
		cfg:        cfg,
	}
}

func (c *Client) headers() http.Header {
	h := make(http.Header)
	h.Set("APCA-API-KEY-ID", c.cfg.APIKey)
	h.Set("APCA-API-SECRET-KEY", c.cfg.APISecret)
	h.Set("Content-Type", "application/json")
	return h
}

func (c *Client) do(ctx context.Context, method, endpoint string, body any, out any) (int, error) {
	if err := c.rateLimit.Wait(ctx); err != nil {
		return 0, err
	}

	var reader io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			return 0, err
		}
		reader = bytes.NewReader(b)
	}

	req, err := http.NewRequestWithContext(ctx, method, endpoint, reader)
	if err != nil {
		return 0, err
	}
	req.Header = c.headers()

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return 0, err
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return resp.StatusCode, err
	}

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		return resp.StatusCode, fmt.Errorf("alpaca API error status=%d body=%s", resp.StatusCode, string(respBody))
	}
	if out == nil {
		return resp.StatusCode, nil
	}
	if err := json.Unmarshal(respBody, out); err != nil {
		return resp.StatusCode, err
	}
	return resp.StatusCode, nil
}

func (c *Client) GetPositions(ctx context.Context) ([]Position, error) {
	endpoint := fmt.Sprintf("%s/v2/positions", strings.TrimSuffix(c.cfg.TradingURL, "/"))
	var positions []Position
	_, err := c.do(ctx, http.MethodGet, endpoint, nil, &positions)
	return positions, err
}

func (c *Client) GetSnapshot(ctx context.Context, symbol string) (*Snapshot, error) {
	endpoint := fmt.Sprintf("%s/v2/stocks/%s/snapshot", strings.TrimSuffix(c.cfg.DataURL, "/"), url.PathEscape(symbol))
	var snapshot Snapshot
	_, err := c.do(ctx, http.MethodGet, endpoint, nil, &snapshot)
	if err != nil {
		return nil, err
	}
	return &snapshot, nil
}

func (c *Client) ClosePosition(ctx context.Context, symbol string) (*ClosePositionResponse, error) {
	endpoint := fmt.Sprintf("%s/v2/positions/%s", strings.TrimSuffix(c.cfg.TradingURL, "/"), url.PathEscape(symbol))
	var out ClosePositionResponse
	status, err := c.do(ctx, http.MethodDelete, endpoint, nil, &out)
	if err != nil {
		if status == http.StatusNotFound {
			return nil, nil
		}
		return nil, err
	}
	return &out, nil
}

func (c *Client) VerifyPositionClosed(ctx context.Context, symbol string, maxRetries int, retryDelay time.Duration) (bool, error) {
	for i := 0; i < maxRetries; i++ {
		endpoint := fmt.Sprintf("%s/v2/positions/%s", strings.TrimSuffix(c.cfg.TradingURL, "/"), url.PathEscape(symbol))
		_, err := c.do(ctx, http.MethodGet, endpoint, nil, &map[string]any{})
		if err != nil {
			if strings.Contains(err.Error(), "status=404") {
				return true, nil
			}
		}
		if i < maxRetries-1 {
			time.Sleep(retryDelay * time.Duration(1<<i))
		}
	}
	return false, nil
}
