"""from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from .market_data_service import MarketDataService
import logging

logger = logging.getLogger(__name__)


class MarketDataView(APIView):
    
    """ """Enhanced Market Data API with dual-source support
    - Primary: Alpaca Market Data API v2 (realtime IEX/SIP)
    - Fallback: Yahoo Finance (historical training data)""" """
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            service = MarketDataService()
            action = request.data.get('action')
            
            if action == 'getRealtimeQuotes':
                symbols = request.data.get('symbols', ['SPY', 'AAPL', 'TSLA', 'MSFT'])
                # Use optimized batch snapshots endpoint
                snapshots = service.get_snapshots(symbols, feed='iex', use_cache=True)
                
                # Convert snapshot format to quotes format for backward compatibility
                quotes_data = {'quotes': {}}
                for symbol, snapshot in snapshots.items():
                    latest_quote = snapshot.get('latestQuote', {})
                    prev_close = snapshot.get('prevDailyBar', {}).get('c')
                    if latest_quote:
                        latest_quote['pc'] = prev_close
                        quotes_data['quotes'][symbol] = latest_quote
                
                # Log status for better visibility
                if quotes_data['quotes']:
                    logger.info(f'✅ Market data loaded for {len(quotes_data["quotes"])} symbols: {", ".join(quotes_data["quotes"].keys())}')
                else:
                    logger.warning(f'⚠️ NO MARKET DATA AVAILABLE - Likely in rate limit cooldown. Requested symbols: {", ".join(symbols[:5])}{"..." if len(symbols) > 5 else ""}')
                
                return Response(quotes_data if quotes_data['quotes'] else {'error': 'Failed to fetch quotes', 'quotes': {}}, status=status.HTTP_200_OK)
            
            elif action == 'getSnapshot':
                symbol = request.data.get('symbol')
                result = service.get_realtime_snapshot(symbol)
                return Response(result or {'error': 'Failed to fetch snapshot'}, status=status.HTTP_200_OK)
            
            elif action == 'getBars':
                symbol = request.data.get('symbol')
                timeframe = request.data.get('timeframe', '5Min')
                limit = request.data.get('limit', 100)
                use_fallback = request.data.get('use_fallback', True)
                
                bars = service.get_bars(symbol, timeframe, limit, use_fallback)
                
                return Response({
                    'symbol': symbol,
                    'timeframe': timeframe,
                    'bars': bars,
                    'count': len(bars),
                    'has_fallback': any(b.get('source') == 'yahoo' for b in bars)
                }, status=status.HTTP_200_OK)
            
            elif action == 'getTrainingData':
                symbol = request.data.get('symbol')
                days = request.data.get('days', 30)
                
                bars = service.get_training_data(symbol, days)
                
                return Response({
                    'symbol': symbol,
                    'training_bars': bars,
                    'count': len(bars),
                    'source': 'yahoo_training' if bars and bars[0].get('source') == 'yahoo_training' else 'alpaca'
                }, status=status.HTTP_200_OK)
            
            else:
                return Response(
                    {'error': 'Invalid action'},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f'Market data error: {str(e)}')
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )"""
