# save_alpaca_orders.py
import os
from decimal import Decimal
from datetime import datetime
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trading_platform.settings')
django.setup()

from alpaca_trade_api.rest import REST
from django.contrib.auth import get_user_model
from api.models import Trade  # replace with your app name

# Alpaca API credentials (use environment variables for security)
API_KEY = os.getenv("APCA_API_KEY_ID")
API_SECRET = os.getenv("APCA_API_SECRET")
BASE_URL = "https://api.alpaca.markets"  # live account

api = REST(API_KEY, API_SECRET, BASE_URL)

# Replace with the user who owns these trades
user = get_user_model().objects.get(email="you@example.com")

def sync_alpaca_orders():
    """
    Fetches all orders from Alpaca and saves filled trades to the DB.
    """
    try:
        orders = api.list_orders(status='all', limit=500, nested=True)  # nested=True gives detailed fills
    except Exception as e:
        print(f"Error fetching Alpaca orders: {e}")
        return

    saved_count = 0
    skipped_count = 0

    for o in orders:
        # Skip orders with no filled quantity
        if Decimal(o.filled_qty) == 0:
            continue

        # Check if this order already exists in DB
        if Trade.objects.filter(broker_deal_id=o.id).exists():
            skipped_count += 1
            continue

        # Determine trade status
        status = "closed" if Decimal(o.filled_qty) == Decimal(o.qty) else "open"

        # Save trade
        trade = Trade.objects.create(
            user=user,
            broker="alpaca_sim",
            instrument_type="stock",  # adjust if you trade other types
            symbol=o.symbol,
            quantity=Decimal(o.filled_qty),
            entry_price=Decimal(o.filled_avg_price),
            side=o.side,
            status=status,
            broker_deal_id=o.id,
            created_at=datetime.fromisoformat(o.created_at),
            closed_at=datetime.fromisoformat(o.filled_at) if status == "closed" else None
        )

        saved_count += 1
        print(f"Saved trade: {trade.symbol}, qty {trade.quantity}, side {trade.side}, status {trade.status}")

    print(f"Sync complete. Saved: {saved_count}, Skipped: {skipped_count}")

if __name__ == "__main__":
    sync_alpaca_orders()
