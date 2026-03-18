# ZimAI Trader — Honest System Assessment

## Current Strategy Summary

- **Type:** Mean-reversion scalping on 1-minute bars
- **Indicators:** RSI + MACD + Bollinger Bands (2 of 3 must agree)
- **Risk/Reward:** 1% stop-loss / 2% take-profit (1:2 ratio)
- **Position size:** 5% of buying power per trade
- **Cycle interval:** 15 seconds
- **Order type:** Limit orders with 0.02% price cushion
- **Quality gate:** Explicit rule engine (loss streak cooldown, BB volatility gate, VIX regime filter, daily P&L soft limit)
- **Trend filter:** 15-minute EMA/SuperTrend blocks buys in confirmed downtrends

## What Works

- **1:2 risk/reward ratio** — only need ~40% win rate to profit: `(0.40 x 2%) - (0.60 x 1%) = +0.2% per trade`
- **Rule engine** — transparent, no overfit, zero training data needed, instant execution
- **Limit orders** — saves 0.05-0.3% per trade vs market orders
- **15-second cycle** — catches price moves before they reverse
- **No RSI override** — RSI is one vote among three, doesn't force trades into crashes
- **VIX filter** — halts trading when market fear is extreme (VIXY > 25)
- **Architecture** — singletons share API caches, rate limiting protects against abuse, agent state survives restarts

## Known Risks & Honest Concerns

### The strategy is mean-reversion on crowded mega-caps
AAPL, MSFT, NVDA, GOOGL, META, TSLA, AMZN — every algorithm, hedge fund, and retail trader watches the same RSI/MACD signals on the same timeframes. When the system sees RSI < 30 on NVDA, thousands of other bots see it too. The edge gets arbitraged away in milliseconds. This system arrives 15 seconds later.

### 2% target vs 1% stop on 1-minute bars is a mismatch
A stock moving 2% intraday might take 30 minutes to 2 hours. During that time, normal price fluctuation can trigger the 1% stop before the 2% target is reached. This is essentially a swing trade with a scalping stop-loss. The tight stop gets triggered by intraday noise, especially on volatile stocks like TSLA and NVDA.

### Paper trading results will overstate performance
Alpaca paper trading gives instant fills at quoted prices with no slippage and no market impact. In live trading:
- Limit orders might not fill (price moves away)
- Spreads widen during volatility (exactly when indicators fire)
- You're competing against firms with co-located servers that see the same signals 1000x faster

### VIX filter uses VIXY (ETF), not actual VIX
VIXY tracks VIX futures, not spot VIX. It decays over time and doesn't react as fast during flash crashes. By the time VIXY moves above 25, you've already been trading in a crash for minutes.

### The ML model still runs in analyze_market_sentiment
The quality gate was replaced with the rule engine, but ML predictions still add/subtract points to the signal score. With a fresh DB and 0 training data, the model won't load (`model_available: False`) so those points won't apply. But if you accumulate 50+ trades and it trains, a model trained on thin data could influence decisions unpredictably.

### No backtest exists
There is zero evidence this strategy works on historical data. This is the single biggest gap. Without a backtest showing the strategy is profitable after commissions over at least 6-12 months of historical data, live trading is a guess.

## What Would Increase Confidence

1. **Backtest before live trading.** Download 1 year of 1-minute bars for the stock pool. Simulate every trade the system would have made. Calculate: win rate, average win, average loss, maximum drawdown, Sharpe ratio. If the backtest doesn't show profit after commissions, the live system won't either.

2. **Trade less-crowded instruments.** Mid-cap stocks ($2B-$10B market cap) with decent volume have more inefficiency than mega-caps. The same RSI/MACD signals have more edge where fewer algorithms are competing.

3. **Widen the stop to 1.5% or use a trailing stop.** A 1% stop on a 1-minute timeframe gets triggered by noise on volatile stocks. A trailing stop (move stop-loss up as profit grows) lets winners run while still protecting downside.

4. **Start with tiny money and track for 30 days.** Don't fund more than you can afford to lose. Track every trade in a spreadsheet. If after 30 trading days and 50+ trades the win rate is below 40%, the strategy doesn't work and no code fix will save it.

## Probability Estimate

**40-50% chance of net profit over 3 months.** Better than the ~20% chance before the architectural fixes, but still a coin flip. The missing piece isn't code — it's a backtest proving the strategy has an edge on historical data. Without that, this is gambling with better risk management.

## Breakeven Math

| Win Rate | Avg Win (2%) | Avg Loss (1%) | Net Per Trade | Monthly (60 trades) |
|----------|-------------|---------------|---------------|---------------------|
| 35% | +0.70% | -0.65% | +0.05% | +3.0% |
| 40% | +0.80% | -0.60% | +0.20% | +12.0% |
| 45% | +0.90% | -0.55% | +0.35% | +21.0% |
| 50% | +1.00% | -0.50% | +0.50% | +30.0% |
| 55% | +1.10% | -0.45% | +0.65% | +39.0% |

Breakeven win rate: ~33%. The system needs to win at least 1 in 3 trades to not lose money. Above 40% it compounds well. Below 33% it bleeds out.
