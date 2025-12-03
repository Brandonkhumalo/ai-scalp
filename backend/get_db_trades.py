#!/usr/bin/env python3
"""
Fetch all open trades from the SQLite DB using Django ORM
"""

import os
import django
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ================================
# Setup Django environment
# ================================
# Replace 'myproject.settings' with your Django project's settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "trading_platform.settings")
django.setup()

from api.models import Trade  # Adjust import based on your app name

def fetch_open_trades():
    """
    Fetch all trades with status='open'
    """
    try:
        open_trades = Trade.objects.filter(status='open').order_by('-created_at')
        if not open_trades.exists():
            logger.info("No open trades found.")
            return []

        trades_list = []
        for trade in open_trades:
            trades_list.append({
                "id": trade.id,
                "user": trade.user.email,
                "symbol": trade.symbol,
                "broker": trade.broker,
                "quantity": float(trade.quantity),
                "entry_price": float(trade.entry_price),
                "side": trade.side,
                "status": trade.status,
                "created_at": trade.created_at.isoformat(),
                "stop_loss": float(trade.stop_loss) if trade.stop_loss else None,
                "take_profit": float(trade.take_profit) if trade.take_profit else None,
            })

        logger.info(f"Fetched {len(trades_list)} open trades")
        return trades_list

    except Exception as e:
        logger.error(f"Error fetching open trades: {e}")
        return []

if __name__ == "__main__":
    trades = fetch_open_trades()
    for t in trades:
        print(t)
