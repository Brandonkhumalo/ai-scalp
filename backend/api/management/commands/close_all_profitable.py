from django.core.management.base import BaseCommand
from accounts.models import User
from api.models import Trade
import requests
import os
from decimal import Decimal

class Command(BaseCommand):
    help = 'Close all profitable positions for all users'

    def handle(self, *args, **kwargs):
        # Get Alpaca credentials
        alpaca_api_key = os.getenv('ALPACA_API_KEY')
        alpaca_secret_key = os.getenv('ALPACA_SECRET_KEY')
        alpaca_base_url = "https://paper-api.alpaca.markets"
        
        headers = {
            'APCA-API-KEY-ID': alpaca_api_key,
            'APCA-API-SECRET-KEY': alpaca_secret_key,
        }
        
        users = User.objects.filter(email__in=['josias@tishanyq.co.zw', 'test@example.com'])
        
        for user in users:
            self.stdout.write(f'\n=== Processing {user.email} ===')
            
            # Get all open Alpaca positions
            try:
                response = requests.get(f'{alpaca_base_url}/v2/positions', headers=headers)
                if response.status_code != 200:
                    self.stdout.write(self.style.ERROR(f'Failed to get positions: {response.text}'))
                    continue
                    
                positions = response.json()
                
                if not positions:
                    self.stdout.write(self.style.WARNING('No open positions'))
                    continue
                
                self.stdout.write(f'Found {len(positions)} open positions')
                
                closed_count = 0
                for pos in positions:
                    symbol = pos['symbol']
                    unrealized_pl = float(pos.get('unrealized_pl', 0))
                    qty = abs(float(pos['qty']))
                    side = pos['side']
                    
                    # Only close profitable positions
                    if unrealized_pl > 0:
                        self.stdout.write(f'Closing profitable position: {symbol} (P/L: ${unrealized_pl:.2f})')
                        
                        # Close position via Alpaca
                        try:
                            close_response = requests.delete(
                                f'{alpaca_base_url}/v2/positions/{symbol}',
                                headers=headers
                            )
                            
                            if close_response.status_code in [200, 207]:
                                self.stdout.write(self.style.SUCCESS(f'✓ Closed {symbol}'))
                                closed_count += 1
                            else:
                                self.stdout.write(self.style.ERROR(f'✗ Failed to close {symbol}: {close_response.text}'))
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f'✗ Error closing {symbol}: {str(e)}'))
                    else:
                        self.stdout.write(f'Skipping {symbol} (P/L: ${unrealized_pl:.2f} - not profitable)')
                
                self.stdout.write(self.style.SUCCESS(f'\nClosed {closed_count} profitable positions for {user.email}'))
                
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Error processing {user.email}: {str(e)}'))
