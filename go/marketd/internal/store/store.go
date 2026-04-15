package store

import (
	"context"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"github.com/shopspring/decimal"
)

type Store struct {
	pool *pgxpool.Pool
}

type Trade struct {
	ID         int64
	UserID     int64
	Symbol     string
	Instrument string
	Side       string
	Status     string
	Quantity   decimal.Decimal
	EntryPrice decimal.Decimal
	ExitPrice  *decimal.Decimal
	ProfitLoss *decimal.Decimal
	CreatedAt  time.Time
}

type User struct {
	ID    int64
	Email string
}

type ReconciliationResult struct {
	GhostsRemoved     int
	PositionsClosed   int
	PositionsSynced   int
	AlpacaPositions   int
	DatabasePositions int
	InSync            bool
}

func New(ctx context.Context, databaseURL string) (*Store, error) {
	pool, err := pgxpool.New(ctx, databaseURL)
	if err != nil {
		return nil, fmt.Errorf("create pgx pool: %w", err)
	}
	if err := pool.Ping(ctx); err != nil {
		return nil, fmt.Errorf("ping postgres: %w", err)
	}
	return &Store{pool: pool}, nil
}

func (s *Store) Close() {
	s.pool.Close()
}

func (s *Store) GetTradingUsers(ctx context.Context) ([]User, error) {
	rows, err := s.pool.Query(ctx, `
		SELECT id, email
		FROM accounts_user
		WHERE ai_trading_enabled = true
	`)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var users []User
	for rows.Next() {
		var u User
		if err := rows.Scan(&u.ID, &u.Email); err != nil {
			return nil, err
		}
		users = append(users, u)
	}
	return users, rows.Err()
}

func (s *Store) GetOpenStockTradesForUser(ctx context.Context, userID int64) ([]Trade, error) {
	rows, err := s.pool.Query(ctx, `
		SELECT id, user_id, symbol, instrument_type, side, status, quantity, entry_price, exit_price, profit_loss, created_at
		FROM api_trade
		WHERE user_id = $1 AND status = 'open' AND instrument_type = 'stock'
		ORDER BY created_at DESC
	`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var out []Trade
	for rows.Next() {
		var t Trade
		if err := rows.Scan(
			&t.ID,
			&t.UserID,
			&t.Symbol,
			&t.Instrument,
			&t.Side,
			&t.Status,
			&t.Quantity,
			&t.EntryPrice,
			&t.ExitPrice,
			&t.ProfitLoss,
			&t.CreatedAt,
		); err != nil {
			return nil, err
		}
		out = append(out, t)
	}
	return out, rows.Err()
}

func (s *Store) MarkTradeClosed(ctx context.Context, tradeID int64, exitPrice, pnl decimal.Decimal) error {
	_, err := s.pool.Exec(ctx, `
		UPDATE api_trade
		SET status = 'closed', exit_price = $2, profit_loss = $3, closed_at = NOW()
		WHERE id = $1
	`, tradeID, exitPrice, pnl)
	return err
}

func (s *Store) CreateTradePNLTransaction(ctx context.Context, userID int64, amount decimal.Decimal, reference string) error {
	_, err := s.pool.Exec(ctx, `
		INSERT INTO api_transaction (user_id, type, amount, currency, reference, status, created_at, updated_at)
		VALUES ($1, 'trade_pnl', $2, 'USD', $3, 'completed', NOW(), NOW())
	`, userID, amount, reference)
	return err
}

func (s *Store) DeleteTrade(ctx context.Context, tradeID int64) error {
	_, err := s.pool.Exec(ctx, `DELETE FROM api_trade WHERE id = $1`, tradeID)
	return err
}
