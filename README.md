# ZimAI Trader

An autonomous AI-powered stock trading platform that combines real-time technical analysis, rule-based risk management, and a 24/7 trading agent to execute scalping strategies on US equities via the Alpaca brokerage API.

Built as a full-stack production system — not a tutorial project — with a React dashboard, Django REST API, autonomous trading loop, position reconciliation, compliance controls (KYC/AML), and role-based access.

---

## Architecture Overview

```
React Dashboard (TypeScript)          Django REST API (Python)
       |                                      |
       |  JWT Auth + REST API                 |
       +--------------------------------------+
                       |
          +------------+------------+
          |            |            |
   Alpaca API    Market Data    PostgreSQL
   (Brokerage)   (Dual-Source)   (Trades, Users,
                                  Audit Logs)
                       |
              Autonomous Agent
              (15-second cycle)
              Position Management
              Risk Engine
```

### Key Design Decisions

- **Microservice-ready monolith** — Clean module boundaries (8 focused service files) that can be split into microservices when scale demands it
- **Alpaca as source of truth** — Database is secondary; positions are always reconciled against the broker's live state
- **Pending trade pattern** — Trades are created with `status='pending'` before the broker order, then promoted to `open` on fill. This eliminates the ghost position problem where a crash between order placement and DB write leaves orphaned broker positions
- **Rule engine over ML** — Replaced a RandomForestClassifier (38 features, prone to overfitting on small datasets) with explicit rules derived from the model's own feature importance analysis. More transparent, zero training data needed, instant execution

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Frontend** | React 18, TypeScript, Vite, Tailwind CSS, shadcn/ui, TanStack Query | Type-safe SPA with real-time data fetching and a component library that ships fast |
| **Backend** | Django 5.2, Django REST Framework | Mature ORM, migration system, and admin panel for a financial application that needs auditability |
| **Database** | PostgreSQL (prod), SQLite (dev) | ACID transactions for financial data; `Decimal` fields for all money — never `float` |
| **Brokerage** | Alpaca Markets API v2 | Commission-free equities with paper trading for development |
| **Market Data** | Alpaca (primary) + Yahoo Finance (fallback) | Dual-source with automatic failover and batch endpoints (1 API call per 50 symbols) |
| **Auth** | JWT with cache-first token blacklisting | Stateless auth with `LocMemCache` blacklist check (eliminates 1 DB query per request) |
| **Rate Limiting** | django-ratelimit | Per-IP (auth: 5/min) and per-user (trading: 30/min, reads: 120/min) |

---

## System Components

### Autonomous Trading Agent
A background process running a 15-second cycle that:
1. Checks all open positions against take-profit (2%) and stop-loss (1%) targets
2. Reconciles database state with Alpaca broker state (detects ghost positions)
3. Pre-screens up to 5 stocks using technical analysis
4. Executes trades when RSI, MACD, and Bollinger Bands agree (2 of 3 majority vote)
5. Persists its state to the database every 20 cycles (survives process restarts)

### Risk Management Engine
```
Rule Engine (trade_rules.py)
  - Loss streak cooldown: Skip trading after 3+ consecutive losses
  - Volatility gate: Halt when Bollinger Band width > 4% (indicators unreliable)
  - VIX regime filter: Halt when VIXY > 25 (extreme market fear)
  - Daily P&L soft limit: Tighten before hitting the 8% hard stop

Position-Level Controls
  - 1:2 risk/reward ratio (1% stop-loss, 2% take-profit)
  - 5% of buying power per trade
  - 25% max concentration per symbol
  - 15-minute trend filter blocks buys in confirmed downtrends
  - Limit orders with 0.02% price cushion (no market order slippage)
```

### Position Reconciliation
Solves the distributed state problem between the database and the broker:
- **Pending trade pattern** — DB record created before broker order, updated after fill
- **Startup reconciliation** — On process restart, checks all `pending` trades against Alpaca
- **Continuous reconciliation** — Every 5 cycles, compares DB positions vs Alpaca positions
- **Grace period** — Orphaned positions auto-close only after 2 consecutive detections (prevents false positives from transient API errors)
- **30-day lookback** — Catches positions closed during weekends/holidays

### DRF Serializers with Decimal Safety
Custom `FloatDecimalField` ensures all financial calculations use `Decimal` internally while serializing to `float` for JSON frontend compatibility. No `float()` arithmetic anywhere in P&L calculations — only at the serialization boundary.

### Compliance Layer
- **KYC/AML** — Know Your Customer records and Anti-Money Laundering alerts with severity levels
- **Audit logging** — Every trade, role change, and admin action logged with user, timestamp, IP address
- **Role-based access** — Admin, compliance officer, trader, user — enforced via DRF permission classes

---

## Project Structure

```
src/                              # React frontend (90 TypeScript files)
  pages/                          # 13 route-level components
  components/                     # 62 reusable components (shadcn/ui)
  contexts/TradingContext.tsx      # Global state (positions, P&L, AI toggle)
  hooks/                          # useAlpacaData, useUserRole, useAuditLog
  lib/api-client.ts               # HTTP client with auto token refresh

backend/                          # Django backend (63 Python files)
  api/
    ai_trading_engine.py          # Signal generation + trade execution (659 lines)
    autonomous_agent_service.py   # 24/7 trading loop with state persistence (909 lines)
    technical_indicators.py       # Pure functions: RSI, MACD, Bollinger, EMA, SuperTrend
    portfolio_service.py          # Concentration checks, position sizing
    scalping_service.py           # Auto-close at profit/loss targets
    trade_rules.py                # Explicit rule engine (loss streak, volatility, VIX)
    market_data_service.py        # Dual-source with batch fetching + rate limiting
    alpaca_account_service.py     # Broker integration with TTL cache + request dedup
    position_reconciliation_service.py  # DB-to-broker state sync
    serializers.py                # DRF serializers with FloatDecimalField
    services.py                   # Singleton service registry
    models.py                     # Trade, Transaction, AuditLog, AgentState, KYC/AML
    views.py                      # 22 REST endpoints with rate limiting
  accounts/
    authentication.py             # JWT with cache-first blacklist
    serializers.py                # User serializers
```

---

## API Endpoints

| Method | Endpoint | Purpose | Rate Limit |
|--------|----------|---------|------------|
| POST | `/api/auth/register/` | User registration | 5/min (IP) |
| POST | `/api/auth/login/` | JWT login | 5/min (IP) |
| POST | `/api/auth/refresh/` | Token refresh | 10/min (IP) |
| GET | `/api/trades/` | List open + closed trades | 120/min (user) |
| GET | `/api/transactions/` | Transaction history | 120/min (user) |
| GET | `/api/alpaca-account/` | Live account data with caching | 120/min (user) |
| GET | `/api/performance-analytics/` | P&L, win rate, Sharpe ratio | 120/min (user) |
| POST | `/api/ai-trading/` | Manual AI trade execution | 30/min (user) |
| POST | `/api/check-profit-taking/` | Trigger scalping check | 30/min (user) |
| GET | `/api/autonomous-agent/status/` | Agent state and metrics | 120/min (user) |
| GET | `/api/admin/platform-overview/` | Platform-wide stats | Admin only |

---

## Running Locally

### Prerequisites
- Python 3.11+
- Node.js 18+
- Alpaca paper trading account (free at alpaca.markets)

### Setup
```bash
# Frontend
npm install
npm run dev

# Backend
cd backend
pip install -r requirements.txt
cp .env.example .env  # Add your DJANGO_SECRET_KEY + Capital demo/live credentials
python manage.py migrate
python manage.py runserver

# Autonomous agent (separate terminal)
python manage.py run_autonomous_agent --interval 15
```

### Environment Variables
```
DJANGO_SECRET_KEY=           # Required — Django will refuse to start without it
BROKER_PROVIDER=capital      # capital (default) or alpaca (legacy fallback)
CAPITAL_TRADING_MODE=demo    # demo or live
CAPITAL_DEMO_API_KEY=        # Capital demo API key
CAPITAL_DEMO_IDENTIFIER=     # Capital demo login identifier/email
CAPITAL_DEMO_PASSWORD=       # Capital demo password
CAPITAL_DEMO_BASE_URL=https://demo-api-capital.backend-capital.com
CAPITAL_LIVE_API_KEY=        # Capital live API key
CAPITAL_LIVE_IDENTIFIER=     # Capital live login identifier/email
CAPITAL_LIVE_PASSWORD=       # Capital live password
CAPITAL_LIVE_BASE_URL=https://api-capital.backend-capital.com
# Optional generic fallback credentials (used if mode-specific values are blank):
CAPITAL_API_KEY=
CAPITAL_IDENTIFIER=
CAPITAL_PASSWORD=
CAPITAL_BASE_URL=
DATABASE_URL=                # PostgreSQL connection string (optional — defaults to SQLite)
DEBUG=True                   # Set False in production
USE_GO_MARKETD=False         # Phase flag for Go marketd cutover
```

### marketd (Go, Shadow Mode)
The repository now includes a Tier-1 Go service scaffold at `go/marketd` for:
- market-hours checks
- scalping target loop
- position reconciliation loop
- Alpaca client + rate limiting

Run it in non-writing shadow mode:

```bash
cd go/marketd
cp .env.example .env
set -a; source .env; set +a
make run-shadow
```

Operational docs:
- `docs/go-port/contract.md`
- `docs/go-port/postgres-migration-runbook.md`
- `docs/go-port/systemd-marketd.service`

### Tests
```bash
cd backend
python manage.py test api.tests -v2    # 17 tests covering P&L, caching, serializers, state persistence
```

### Validation Pipeline (New)
Run these before trusting ML metrics or deploying strategy changes:

```bash
cd backend

# 1) Audit data integrity (duplicates, side/status casing, P&L mismatches)
python manage.py audit_trade_data --output-json backend/reports/data_audit.json

# Optional: normalize symbol/side/status casing in-place
python manage.py audit_trade_data --apply-normalization

# 2) Walk-forward out-of-sample validation with execution costs
python manage.py run_walk_forward_validation \
  --min-train-trades 40 \
  --test-size 20 \
  --step-size 20 \
  --spread-bps 2 \
  --slippage-bps 3 \
  --commission-per-share 0.0035
```

The walk-forward command writes a JSON report to `backend/reports/` with:
- Fold-by-fold train/test windows (chronological, no leakage)
- Baseline vs ML-gated out-of-sample metrics
- Net P&L after spread/slippage/commission assumptions
- Deployment gate checks (`deployment_ready`) for objective go/no-go decisions

---

## Engineering Highlights

**Things I'd point to in a code review:**

- **Cache-first token blacklisting** ([authentication.py](backend/accounts/authentication.py)) — Hashes JWT tokens with SHA-256, checks LocMemCache before hitting the DB. Logout populates both layers. Eliminates a database query on every authenticated request.

- **Pending trade pattern** ([ai_trading_engine.py](backend/api/ai_trading_engine.py)) — Creates a `pending` DB row before placing the broker order, then promotes to `open` on fill or `failed` on error. Startup reconciliation catches any trades left in `pending` from a crash. This solves the distributed state consistency problem without a message queue.

- **Singleton service registry** ([services.py](backend/api/services.py)) — Module-level instances ensure all views and the background agent share the same in-memory caches and rate-limit counters. Replaced 16 per-request instantiation sites.

- **Decimal-only financial arithmetic** ([serializers.py](backend/api/serializers.py)) — Custom `FloatDecimalField` keeps all server-side math in `Decimal` and converts to `float` only at the JSON serialization boundary. Prevents the rounding errors that accumulate over hundreds of trades.

- **Rule engine over ML** ([trade_rules.py](backend/api/trade_rules.py)) — After building and tuning a RandomForest model, analyzed feature importances and found the top signal was simply "don't trade during loss streaks" (23% importance). Replaced the model with 4 explicit rules that are more transparent, can't overfit, and need zero training data.

- **Dual-source market data with batch optimization** ([market_data_service.py](backend/api/market_data_service.py)) — Alpaca primary with Yahoo Finance fallback. Batch endpoints fetch 50 symbols per API call instead of 50 individual calls. 15-second cooldown on rate limits with automatic fallback to cached data.

---

## What I Learned Building This

- **Risk/reward matters more than win rate.** Started with 1.5% profit target / 2% stop-loss (needed 57% win rate to break even). Flipped to 1% stop / 2% profit — now only need 40%. The math is more important than the algorithm.
- **ML isn't always the answer.** A RandomForest with 38 features on 50-150 training samples was overfitting and adding false confidence. Three explicit rules outperform it because they encode domain knowledge directly instead of trying to learn it from insufficient data.
- **Distributed state is the hardest problem.** The broker and the database can disagree. The pending trade pattern, startup reconciliation, and continuous reconciliation were the most challenging engineering problems — and the most important for a system handling real money.
- **Cache everything, but cache correctly.** Token blacklist caching, market data caching, account info caching, and singleton service caches each have different TTLs tuned to their data freshness requirements (15s for orders, 30s for positions, 60s for account info).

---

## License

Private project — not open source.
