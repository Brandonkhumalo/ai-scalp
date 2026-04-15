-- name: ListTradingUsers :many
SELECT id, email
FROM accounts_user
WHERE ai_trading_enabled = true;
