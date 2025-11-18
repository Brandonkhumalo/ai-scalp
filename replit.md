# ZimAI Trader - AI-Powered Trading Platform

## Overview

ZimAI Trader is an AI-powered trading platform that enables automated trading on US stock markets through Alpaca's paper trading API. The platform features:

- **Autonomous AI Trading Agent**: Runs 24/7 during market hours, executing trades based on machine learning predictions and technical analysis
- **Multi-Market Support**: Focuses on US markets (NYSE/NASDAQ) with timezone-aware market hours tracking
- **Machine Learning Engine**: Random Forest classifier that learns from historical trade data to improve predictions
- **Real-time Market Data**: Integration with Alpaca Market Data API v2 for live quotes and snapshots
- **Advanced Risk Management**: Stop-loss, take-profit, trailing stops, and position sizing
- **User Management**: Role-based access control (Admin, Compliance Officer, Trader, User)

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture

**Technology Stack:**
- React 18.3 with TypeScript
- Vite for build tooling and development server
- TanStack Query (React Query) for server state management
- React Router for client-side routing
- Shadcn/UI component library (Radix UI primitives)
- Tailwind CSS for styling

**Design Decisions:**
- **SPA Architecture**: Single-page application with client-side routing to provide smooth navigation
- **Component-Based UI**: Reusable components built on Radix UI primitives for accessibility
- **State Management**: Context API for trading state (`TradingContext`), React Query for server state
- **Cache Busting**: Aggressive no-cache headers and version stamping to prevent stale UI (`vite-plugin-version.ts`)
- **Error Handling**: ErrorBoundary component to catch and display React errors gracefully
- **Responsive Design**: Mobile-first approach with container-based layouts

**Key Features:**
- Real-time market data visualization (disabled polling to reduce API calls)
- Trading dashboard with position management
- AI trading toggle controls
- Autonomous agent status monitoring
- Profile and balance history views

### Backend Architecture

**Technology Stack:**
- Django 5.2.7 with Django REST Framework
- PostgreSQL database (via environment configuration)
- JWT authentication (custom implementation)
- Gunicorn WSGI server for production
- Background worker for autonomous trading agent

**Design Patterns:**
- **Service Layer Pattern**: Business logic separated into service classes (`AITradingEngine`, `MarketDataService`, `MLTradingModel`, `AlpacaAccountService`)
- **Authentication Middleware**: Custom JWT authentication extending DRF's `BaseAuthentication`
- **Role-Based Access Control**: `UserRole` model with permission classes (`IsAdmin`, `IsComplianceOfficer`)
- **Background Processing**: Autonomous agent runs as separate thread with continuous market monitoring

**Core Services:**

1. **AI Trading Engine** (`ai_trading_engine.py`):
   - Executes trades based on ML predictions and technical indicators (RSI, MACD, Bollinger Bands)
   - **Trend Detection Filters** (v4.0 - Nov 2025):
     * EMA 50/200 crossover trend detection on 1-minute timeframe
     * SuperTrend indicator for momentum confirmation
     * Higher timeframe (1H) trend check blocks trades against strong trends (70%+ confidence)
     * Hard-blocks prevent execution when signals contradict major trend direction
   - Integrates with Alpaca trading API for order execution
   - Implements advanced risk management (position sizing, stop-loss, take-profit, trailing stops)

2. **Machine Learning Service** (`ml_training_service.py`):
   - Random Forest classifier with **38 features** (upgraded from 30 features - Nov 2025)
   - **Loss Pattern Learning** (v4.0):
     * Drawdown zone detection (is_in_drawdown, drawdown_severity)
     * Volatility spike recognition (is_volatility_spike, volatility_regime)
     * High-loss condition avoidance (is_high_loss_condition, recent_loss_streak)
     * Similar past loss pattern matching (similar_past_losses, loss_pattern_score)
   - Chronological feature extraction ensures accurate cumulative PnL and loss streak tracking
   - Automatic retraining every 24 hours when sufficient trade data exists
   - Versioned model storage with performance metrics tracking and automatic old-model invalidation
   - Bootstrap mode allows trading without ML model (falls back to technical analysis)

3. **Market Data Service** (`market_data_service.py`):
   - Dual-source: Alpaca Market Data API v2 (primary) and Yahoo Finance (fallback)
   - Thread-safe caching with TTL-based expiration (60s for quotes, 30s for snapshots)
   - Batch fetching optimization to reduce API calls from 1200/min to <65/min
   - Rate limit handling with exponential backoff

4. **Alpaca Account Service** (`alpaca_account_service.py`):
   - Account balance and position management
   - Intelligent caching system with category-specific TTLs (60s for account, 30s for positions)
   - Request deduplication to prevent redundant API calls

5. **Autonomous Agent Service** (`autonomous_agent_service.py`):
   - 24/7 operation during market hours (9:30 AM - 4:00 PM EST, Mon-Fri)
   - Per-user reconciliation to prevent orphaned positions
   - Multi-timezone market hours tracking
   - Configurable check intervals (default 60s)

6. **Market Hours Service** (`market_hours_service.py`):
   - Timezone-aware market open/close detection
   - Currently supports US markets only (NYSE/NASDAQ)
   - Extensible for future international markets

**Database Models:**
- `User`: Custom user model with trading balances, AI toggle, approval workflow
- `Trade`: Trade execution records with P&L tracking
- `Transaction`: Deposit/withdrawal/P&L transactions
- `AuditLog`: Immutable audit trail for compliance
- `UserRole`: Role assignments for RBAC
- `ModelRegistry`: ML model version tracking
- `TradableInstrument`: Supported trading symbols
- `BrokerAccountSummary`: Broker account snapshots
- `BlacklistedToken`: JWT token revocation

**API Design:**
- RESTful endpoints under `/api/` prefix
- JWT bearer token authentication
- Versioned responses for cache busting
- CORS enabled for cross-origin requests
- Health check endpoint for monitoring

### Deployment Architecture

**Deployment Requirements:**
- **Reserved VM**: Required for background autonomous trading agent (Autoscale does not support background processes)
- **Port 5000**: Web server listens on port 5000
- **Build Command**: `bash build-production.sh`
- **Run Command**: `bash start-production.sh`

**Static Files:**
- Vite builds React app to `dist/` with hash-based asset names
- Django serves static files from `backend/staticfiles/` in production
- Base path `/static/` for production assets

**Environment Variables:**
- `DJANGO_SECRET_KEY`: Django secret key (required)
- `ALPACA_API_KEY`: Alpaca API key for trading
- `ALPACA_API_SECRET`: Alpaca API secret
- `DATABASE_URL`: PostgreSQL connection string (optional, uses SQLite if not set)
- `DEBUG`: Set to `True` for development (defaults to `False`)
- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts (defaults to `*`)

**Cache Control:**
- Custom `NoCacheMiddleware` prevents browser caching of HTML
- Aggressive no-cache headers for index.html to prevent stale UI errors
- Service worker cleanup on page load

**Security:**
- CSRF protection enabled
- Secure cookies in production (HTTPS only)
- HSTS headers for HTTPS enforcement
- XSS protection headers
- CORS configured for cross-origin requests

## External Dependencies

### Third-Party Services

1. **Alpaca Markets API**
   - **Purpose**: Stock trading and market data
   - **Integration**: Paper trading API for simulated trading
   - **Endpoints Used**:
     - Trading API: Order submission, position management
     - Market Data API v2: Real-time quotes, snapshots, historical bars
   - **Authentication**: API key + secret (HMAC headers)
   - **Rate Limits**: Optimized with caching and batch requests (<65 calls/min)

2. **Yahoo Finance** (yfinance library)
   - **Purpose**: Fallback market data source
   - **Use Case**: Historical data for ML training when Alpaca is unavailable
   - **Integration**: Python library for data fetching

### Python Dependencies

**Core Framework:**
- `django==5.2.7`: Web framework
- `djangorestframework`: REST API framework
- `gunicorn`: WSGI production server

**Machine Learning:**
- `scikit-learn==1.7.2`: Random Forest classifier
- `numpy==1.26.4`: Numerical computing
- `pandas==2.2.2`: Data manipulation
- `joblib==1.3.2`: Model serialization
- `scipy==1.12.0`: Scientific computing

**Authentication:**
- `PyJWT`: JWT token generation/validation
- Custom JWT authentication class

**Market Data:**
- `yfinance`: Yahoo Finance API client
- `requests`: HTTP client for Alpaca API

**Database:**
- `psycopg2`: PostgreSQL adapter (optional)
- SQLite (default, no external dependency)

### Frontend Dependencies

**UI Framework:**
- `react==18.3.1`: Core library
- `react-dom==18.3.1`: DOM rendering
- `react-router-dom`: Client-side routing

**State Management:**
- `@tanstack/react-query==5.83.0`: Server state management
- Context API for global trading state

**UI Components:**
- `@radix-ui/*`: Accessible component primitives (20+ packages)
- `lucide-react==0.462.0`: Icon library
- `tailwindcss`: Utility-first CSS framework
- `class-variance-authority`: Variant-based component styling
- `clsx`: Conditional class names

**Forms:**
- `react-hook-form`: Form state management
- `@hookform/resolvers`: Form validation
- `zod`: Schema validation

**Utilities:**
- `date-fns==3.6.0`: Date manipulation
- `embla-carousel-react`: Carousel component

**Build Tools:**
- `vite`: Build tool and dev server
- `@vitejs/plugin-react-swc`: React plugin with SWC compiler
- `typescript`: Type checking
- `eslint`: Code linting

### Database

**Current Setup:**
- SQLite (default, file-based)
- PostgreSQL support via `DATABASE_URL` environment variable

**Schema Management:**
- Django ORM for migrations
- Models defined in `api/models.py` and `accounts/models.py`

**Future Considerations:**
- The application uses Django's ORM, which is database-agnostic
- Drizzle ORM is not currently used, but could be added for TypeScript-based schema management
- PostgreSQL recommended for production (better concurrency, JSON support, full-text search)

### Monitoring & Logging

**Logging:**
- Python `logging` module with structured logs
- API call metrics logging (efficiency tracking)
- Trade execution logs with P&L tracking

**Health Checks:**
- `/api/health/` endpoint for uptime monitoring
- Autonomous agent status endpoint

**Performance Tracking:**
- API call counters for rate limit monitoring
- Cache hit/miss metrics
- ML model performance metrics (accuracy, precision, recall)