-- name: ListOpenStockTradesByUser :many
SELECT id, user_id, symbol, instrument_type, side, status, quantity, entry_price, exit_price, profit_loss, created_at
FROM api_trade
WHERE user_id = $1 AND status = 'open' AND instrument_type = 'stock'
ORDER BY created_at DESC;

-- name: MarkTradeClosed :exec
UPDATE api_trade
SET status = 'closed', exit_price = $2, profit_loss = $3, closed_at = NOW()
WHERE id = $1;

-- name: DeleteTrade :exec
DELETE FROM api_trade WHERE id = $1;
