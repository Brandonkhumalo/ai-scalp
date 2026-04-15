-- name: CreateTradePNLTransaction :exec
INSERT INTO api_transaction (user_id, type, amount, currency, reference, status, created_at, updated_at)
VALUES ($1, 'trade_pnl', $2, 'USD', $3, 'completed', NOW(), NOW());
