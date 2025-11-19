# ZimAI Trader - AI-Powered Trading Platform

## Overview
ZimAI Trader is an AI-powered platform designed for automated trading on US stock markets using Alpaca's paper trading API. Its core purpose is to execute trades based on machine learning predictions and technical analysis, aiming to generate profits autonomously. Key capabilities include 24/7 operation during market hours, real-time market data integration, advanced risk management features, and a sophisticated machine learning engine that learns from historical trade data to refine its predictions. The project aims to provide a robust, AI-driven solution for automated stock market participation.

## Recent Changes

### November 19, 2025: Trading Quality Improvements
**Objective:** Reduce losing trades and improve profit staying power.

**Key Changes:**
1. **ML Confidence Threshold**: Raised from 60% to 75% - system now only executes high-quality predictions
2. **FINAL GUARD Protection**: Lowered trend confidence requirement from 70% to 60% to catch more falling stocks
3. **Profit Target**: Increased from 1% to 1.5% to give positions better staying power
4. **ML Training Data**: Removed [:100] trade limit to train on ALL closed trades (374 trades)
5. **Enhanced Logging**: Added STRONG/MEDIUM labels to ML predictions for better visibility

**Impact:**
- Trades with <75% ML confidence are now rejected (previously accepted at 60%)
- More falling stocks blocked by FINAL GUARD (60% vs 70% trend confidence requirement)
- ML model trained on complete trading history (90% profitable ratio with 10% losing trades included)
- Positions have 50% more profit target room before auto-closing

## User Preferences
Preferred communication style: Simple, everyday language.

## System Architecture

### Frontend Architecture
The frontend is a Single-Page Application (SPA) built with React 18.3 and TypeScript, utilizing Vite for tooling. It employs TanStack Query for server state management, React Router for navigation, and Shadcn/UI (based on Radix UI primitives) for a component-based, accessible, and responsive user interface styled with Tailwind CSS. Key features include real-time market data visualization, a trading dashboard, AI trading controls, and user account management.

### Backend Architecture
The backend is developed with Django 5.2.7 and Django REST Framework, using PostgreSQL for data storage. It features a custom JWT authentication system and runs with Gunicorn in production. The architecture incorporates a Service Layer Pattern to separate business logic and includes a background worker for the autonomous trading agent.

**Core Services:**
- **AI Trading Engine:** Executes trades based on ML predictions (≥75% confidence required) and technical indicators (RSI, MACD, Bollinger Bands). It includes advanced logic for RSI override, smart position sizing to manage concentration risk (25% max concentration), 1.5% profit target scalping, 2% stop-loss, and multi-timeframe trend detection filters (FINAL GUARD at ≥60% trend confidence) to prevent trades against strong market trends.
- **Machine Learning Service:** Employs a Random Forest classifier with 38 features, focusing on learning from loss patterns, drawdown detection, and volatility recognition. It supports automatic retraining on ALL closed trades, versioned model storage, and can operate in a bootstrap mode using only technical analysis if no ML model is available. Current model version 4.1 trained on 374 trades with 90% profitable ratio.
- **Market Data Service:** Gathers real-time and historical market data from Alpaca Market Data API v2 (primary) and Yahoo Finance (fallback), with thread-safe caching and rate limit handling.
- **Alpaca Account Service:** Manages account balance and positions with intelligent caching and request deduplication.
- **Autonomous Agent Service:** Operates 24/7 during US market hours, performing per-user reconciliation and supporting multi-timezone market hours tracking.
- **Market Hours Service:** Provides timezone-aware market open/close detection for US markets.

**Database Models:** Custom Django models handle users, trades, transactions, audit logs, user roles, ML model registry, tradable instruments, broker account summaries, and blacklisted JWT tokens.

**API Design:** RESTful endpoints with JWT authentication, versioned responses, CORS support, and a health check endpoint.

### Deployment Architecture
The platform requires a reserved VM for the continuous operation of the autonomous trading agent. It utilizes `bash build-production.sh` and `bash start-production.sh` for deployment, serving static files from `dist/` (frontend) and `backend/staticfiles/` (Django). Environment variables manage sensitive configurations, and aggressive cache control mechanisms are in place. Security measures include CSRF protection, secure cookies, HSTS, XSS protection, and CORS configuration.

## External Dependencies

### Third-Party Services
1.  **Alpaca Markets API**: Used for simulated stock trading (paper trading API) and real-time market data (Market Data API v2), including order execution, position management, quotes, snapshots, and historical bars. Authentication via API key and secret.
2.  **Yahoo Finance**: Serves as a fallback market data source, primarily for historical data used in ML training.

### Python Dependencies
-   **Core Framework**: `django`, `djangorestframework`, `gunicorn`.
-   **Machine Learning**: `scikit-learn` (Random Forest), `numpy`, `pandas`, `joblib`, `scipy`.
-   **Authentication**: `PyJWT`.
-   **Market Data**: `yfinance`, `requests`.
-   **Database**: `psycopg2` (for PostgreSQL).

### Frontend Dependencies
-   **UI Framework**: `react`, `react-dom`, `react-router-dom`.
-   **State Management**: `@tanstack/react-query`, React Context API.
-   **UI Components**: `@radix-ui/*`, `lucide-react`, `tailwindcss`, `class-variance-authority`, `clsx`.
-   **Forms**: `react-hook-form`, `@hookform/resolvers`, `zod`.
-   **Utilities**: `date-fns`, `embla-carousel-react`.
-   **Build Tools**: `vite`, `@vitejs/plugin-react-swc`, `typescript`, `eslint`.

### Database
The project primarily uses SQLite by default, with robust support for PostgreSQL via the `DATABASE_URL` environment variable. Django ORM handles schema migrations.

### Monitoring & Logging
Utilizes Python's `logging` module for structured logs, API call metrics, and trade execution tracking. A `/api/health/` endpoint is provided for uptime monitoring.