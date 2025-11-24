import os
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
import logging

logger = logging.getLogger(__name__)


class AlpacaMarketDataView(APIView):
    permission_classes = [IsAuthenticated]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.alpaca_api_key = os.getenv('ALPACA_API_KEY')
        self.alpaca_api_secret = os.getenv('ALPACA_API_SECRET')
        self.alpaca_data_url = 'https://data.alpaca.markets'
        self.alpaca_trading_url = 'https://api.alpaca.markets'

    def get_alpaca_headers(self):
        return {
            'APCA-API-KEY-ID': self.alpaca_api_key,
            'APCA-API-SECRET-KEY': self.alpaca_api_secret,
            'Content-Type': 'application/json',
        }

    def post(self, request):
        try:
            logger.info('Alpaca market data function invoked')

            if not self.alpaca_api_key or not self.alpaca_api_secret:
                logger.error('Alpaca API credentials not configured')
                return Response(
                    {'error': 'Alpaca API credentials not configured'},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )

            data = request.data
            action = data.get('action')
            symbol = data.get('symbol')
            symbols = data.get('symbols', [])
            qty = data.get('qty')
            side = data.get('side')
            order_type = data.get('type', 'market')
            time_in_force = data.get('time_in_force', 'day')
            instrument_type = data.get('instrument_type', 'stock')

            headers = self.get_alpaca_headers()
            response = None

            if action == 'getQuote':
                # Get latest quote for a symbol
                endpoint = f"{self.alpaca_data_url}/v2/stocks/{symbol}/quotes/latest"
                response = requests.get(endpoint, headers=headers)

            elif action == 'getQuotes':
                # Get quotes for multiple symbols
                symbol_list = ','.join(symbols)
                endpoint = f"{self.alpaca_data_url}/v2/stocks/quotes/latest?symbols={symbol_list}"
                response = requests.get(endpoint, headers=headers)

            elif action == 'placeOrder':
                # Place a paper trade order
                order_payload = {
                    'symbol': symbol,
                    'qty': qty,
                    'side': side,
                    'type': order_type,
                    'time_in_force': time_in_force,
                }
                endpoint = f"{self.alpaca_trading_url}/v2/orders"
                response = requests.post(endpoint, headers=headers, json=order_payload)

            elif action == 'getPositions':
                # Get all open positions
                endpoint = f"{self.alpaca_trading_url}/v2/positions"
                response = requests.get(endpoint, headers=headers)

            elif action == 'getAccount':
                # Get account information
                endpoint = f"{self.alpaca_trading_url}/v2/account"
                response = requests.get(endpoint, headers=headers)

            elif action == 'getOrders':
                # Get recent orders
                endpoint = f"{self.alpaca_trading_url}/v2/orders?status=all&limit=50"
                response = requests.get(endpoint, headers=headers)

            elif action == 'searchAssets':
                # Search for tradeable assets (stocks and options only)
                endpoint = f"{self.alpaca_data_url}/v2/assets?status=active&asset_class=us_equity"
                response = requests.get(endpoint, headers=headers)

            elif action == 'getSnapshot':
                # Get market snapshot with depth data
                endpoint = f"{self.alpaca_data_url}/v2/stocks/{symbol}/snapshot"
                response = requests.get(endpoint, headers=headers)

            elif action == 'getOrderBook':
                # Get order book depth (not available for stocks)
                return Response(
                    {'error': 'Order book not available for stocks/options'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            elif action == 'getLatestTrades':
                # Get latest trades for depth analysis
                endpoint = f"{self.alpaca_data_url}/v2/stocks/{symbol}/trades/latest"
                response = requests.get(endpoint, headers=headers)

            elif action == 'getBars':
                # Get historical bars/candles
                timeframe = data.get('timeframe', '1Min')
                start = data.get('start')
                end = data.get('end')
                endpoint = f"{self.alpaca_data_url}/v2/stocks/{symbol}/bars?timeframe={timeframe}"
                if start:
                    endpoint += f"&start={start}"
                if end:
                    endpoint += f"&end={end}"
                response = requests.get(endpoint, headers=headers)

            elif action == 'getOptionsChain':
                # Get options chain for a symbol
                underlying_symbols = data.get('underlying_symbols', symbol)
                expiration_date = data.get('expiration_date')
                endpoint = f"{self.alpaca_data_url}/v2/options/contracts?underlying_symbols={underlying_symbols}"
                if expiration_date:
                    endpoint += f"&expiration_date={expiration_date}"
                response = requests.get(endpoint, headers=headers)

            elif action == 'getOptionsSnapshot':
                # Get options snapshot with Greeks and IV
                option_symbol = data.get('option_symbol', symbol)
                endpoint = f"{self.alpaca_data_url}/v2/options/snapshots/{option_symbol}"
                response = requests.get(endpoint, headers=headers)

            elif action == 'getMarketCalendar':
                # Get market calendar
                start = data.get('start')
                end = data.get('end')
                endpoint = f"{self.alpaca_data_url}/v2/calendar"
                if start:
                    endpoint += f"?start={start}"
                if end:
                    endpoint += f"&end={end}"
                response = requests.get(endpoint, headers=headers)

            elif action == 'getInternationalAssets':
                # Get international assets (supported markets)
                exchange = data.get('exchange', 'NASDAQ')
                endpoint = f"{self.alpaca_data_url}/v2/assets?status=active&exchange={exchange}"
                response = requests.get(endpoint, headers=headers)

            else:
                return Response(
                    {'error': 'Invalid action'},
                    status=status.HTTP_400_BAD_REQUEST
                )

            if response.status_code != 200:
                error_text = response.text
                logger.error(f'Alpaca API error for {action}: {response.status_code} {error_text}')
                logger.error(f'Endpoint called: {endpoint if "endpoint" in locals() else "unknown"}')
                
                # Provide user-friendly error message
                if response.status_code == 404:
                    return Response(
                        {
                            'error': 'Data not available',
                            'message': f'The requested data for {symbol if symbol else "this symbol"} is not available. The market may be closed or the symbol may not exist.',
                            'action': action,
                            'status_code': 404
                        },
                        status=status.HTTP_200_OK
                    )
                
                return Response(
                    {'error': 'Alpaca API error', 'details': error_text, 'action': action},
                    status=response.status_code
                )

            result_data = response.json()
            return Response(result_data, status=status.HTTP_200_OK)

        except Exception as e:
            logger.error(f'Error in alpaca-market-data function: {str(e)}')
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
