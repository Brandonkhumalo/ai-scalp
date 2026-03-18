"""
Pure technical indicator functions extracted from AITradingEngine.

All functions are stateless — they accept data arrays and return computed values.
No external imports are needed; only basic Python math is used.
"""


def calculate_rsi(prices, period=14):
    """Calculate Relative Strength Index"""
    if len(prices) < period + 1:
        return 50

    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi


def calculate_macd(prices, fast=12, slow=26, signal=9):
    """Calculate MACD (Moving Average Convergence Divergence)"""
    if len(prices) < slow + signal:
        return 0, 0, 0

    # Calculate EMAs
    def ema(data, period):
        if len(data) < period:
            return []
        multiplier = 2 / (period + 1)
        ema_values = [sum(data[:period]) / period]
        for price in data[period:]:
            ema_values.append((price - ema_values[-1]) * multiplier + ema_values[-1])
        return ema_values

    # Calculate fast and slow EMAs
    fast_ema_values = ema(prices, fast)
    slow_ema_values = ema(prices, slow)

    # Align by trimming fast EMA to match slow EMA length
    # slow EMA starts later, so we need to offset fast EMA
    offset = slow - fast
    aligned_fast_ema = fast_ema_values[offset:]

    # Calculate MACD line (fast - slow)
    macd_values = [aligned_fast_ema[i] - slow_ema_values[i] for i in range(len(slow_ema_values))]

    # Calculate signal line (EMA of MACD)
    signal_values = ema(macd_values, signal)

    if not signal_values:
        return 0, 0, 0

    macd_line = macd_values[-1]
    signal_line = signal_values[-1]
    histogram = macd_line - signal_line

    return macd_line, signal_line, histogram


def calculate_bollinger_bands(prices, period=20, std_dev=2):
    """Calculate Bollinger Bands"""
    if len(prices) < period:
        return prices[-1], prices[-1], prices[-1]

    recent_prices = prices[-period:]
    sma = sum(recent_prices) / period
    variance = sum((p - sma) ** 2 for p in recent_prices) / period
    std = variance ** 0.5

    upper_band = sma + (std_dev * std)
    lower_band = sma - (std_dev * std)

    return upper_band, sma, lower_band


def calculate_ema(prices, period):
    """Calculate Exponential Moving Average"""
    if len(prices) < period:
        return None

    multiplier = 2 / (period + 1)
    ema_values = [sum(prices[:period]) / period]

    for price in prices[period:]:
        ema_values.append((price - ema_values[-1]) * multiplier + ema_values[-1])

    return ema_values[-1]


def calculate_ema_trend(prices):
    """
    Calculate EMA 50/200 trend filter.
    Returns: 'uptrend', 'downtrend', or 'neutral'
    """
    if len(prices) < 200:
        return 'neutral'  # Not enough data for trend detection

    ema_50 = calculate_ema(prices, 50)
    ema_200 = calculate_ema(prices, 200)

    if ema_50 is None or ema_200 is None:
        return 'neutral'

    # Golden cross (EMA 50 above EMA 200) = uptrend
    if ema_50 > ema_200 * 1.01:  # 1% buffer to avoid whipsaws
        return 'uptrend'
    # Death cross (EMA 50 below EMA 200) = downtrend
    elif ema_50 < ema_200 * 0.99:
        return 'downtrend'
    else:
        return 'neutral'


def calculate_supertrend(bars, period=10, multiplier=3):
    """
    Calculate SuperTrend indicator.
    Returns: 'uptrend', 'downtrend', or 'neutral', and the current supertrend value.
    """
    if len(bars) < period:
        return 'neutral', None

    # Extract high, low, close prices
    highs = [float(bar['h']) for bar in bars]
    lows = [float(bar['l']) for bar in bars]
    closes = [float(bar['c']) for bar in bars]

    # Calculate ATR (Average True Range)
    true_ranges = []
    for i in range(1, len(bars)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i-1]),
            abs(lows[i] - closes[i-1])
        )
        true_ranges.append(tr)

    if len(true_ranges) < period:
        return 'neutral', None

    # Simple moving average of true range
    atr = sum(true_ranges[-period:]) / period

    # Calculate basic upper and lower bands
    hl_avg = (highs[-1] + lows[-1]) / 2
    basic_upper = hl_avg + (multiplier * atr)
    basic_lower = hl_avg - (multiplier * atr)

    # Determine trend based on close price vs bands
    current_price = closes[-1]

    if current_price > basic_upper:
        return 'uptrend', basic_upper
    elif current_price < basic_lower:
        return 'downtrend', basic_lower
    else:
        return 'neutral', hl_avg
