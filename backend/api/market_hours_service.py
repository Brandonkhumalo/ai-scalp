import logging
from datetime import datetime, time
from zoneinfo import ZoneInfo
from typing import Dict, List, Set

logger = logging.getLogger(__name__)


class MarketHoursService:
    """
    Market hours service for Alpaca US stock trading.
    Alpaca supports US markets only (NYSE/NASDAQ): 9:30 AM - 4:00 PM EST, Monday-Friday
    """
    
    MARKET_SCHEDULES = {
        'US': {
            'name': 'US Markets (NYSE/NASDAQ)',
            'timezone': 'America/New_York',
            'open': time(9, 30),
            'close': time(16, 0),
            'days': [0, 1, 2, 3, 4],  # Monday-Friday
            'broker': 'capital',
            'stocks': ['US']
        }
    }
    
    @classmethod
    def get_open_markets(cls) -> Dict[str, dict]:
        """Get all currently open markets"""
        now_utc = datetime.now(ZoneInfo('UTC'))
        open_markets = {}
        
        for market_id, schedule in cls.MARKET_SCHEDULES.items():
            if cls.is_market_open(market_id):
                market_tz = ZoneInfo(schedule['timezone'])
                market_time = now_utc.astimezone(market_tz)
                
                open_markets[market_id] = {
                    **schedule,
                    'current_time': market_time.strftime('%Y-%m-%d %H:%M:%S %Z'),
                    'local_weekday': market_time.strftime('%A')
                }
                
        return open_markets
    
    @classmethod
    def is_market_open(cls, market_id: str = 'US') -> bool:
        """Check if US market is currently open (9:30 AM - 4:00 PM EST, Mon-Fri)"""
        if market_id not in cls.MARKET_SCHEDULES:
            return False
            
        schedule = cls.MARKET_SCHEDULES[market_id]
        market_tz = ZoneInfo(schedule['timezone'])
        now_utc = datetime.now(ZoneInfo('UTC'))
        market_time = now_utc.astimezone(market_tz)
        
        weekday = market_time.weekday()
        current_time = market_time.time()
        
        return (
            weekday in schedule['days'] and
            schedule['open'] <= current_time <= schedule['close']
        )
    
    @classmethod
    def get_next_market_open(cls, market_id: str = 'US') -> str:
        """Get human-readable text for when market opens next"""
        if market_id not in cls.MARKET_SCHEDULES:
            return "Unknown market"
            
        schedule = cls.MARKET_SCHEDULES[market_id]
        market_tz = ZoneInfo(schedule['timezone'])
        now_utc = datetime.now(ZoneInfo('UTC'))
        market_time = now_utc.astimezone(market_tz)
        
        if cls.is_market_open(market_id):
            return f"Market is currently OPEN (closes at {schedule['close'].strftime('%H:%M')} {schedule['timezone']})"
        
        weekday = market_time.weekday()
        current_time = market_time.time()
        
        # If it's a weekday and before market open
        if weekday in schedule['days'] and current_time < schedule['open']:
            return f"Opens today at {schedule['open'].strftime('%H:%M')} {schedule['timezone']}"
        
        # If it's Friday after close
        if weekday == 4:
            return f"Opens Monday at {schedule['open'].strftime('%H:%M')} {schedule['timezone']}"
        
        # If it's Saturday
        if weekday == 5:
            return f"Opens Monday at {schedule['open'].strftime('%H:%M')} {schedule['timezone']}"
        
        # If it's Sunday
        if weekday == 6:
            return f"Opens Monday at {schedule['open'].strftime('%H:%M')} {schedule['timezone']}"
        
        # Otherwise opens tomorrow
        return f"Opens tomorrow at {schedule['open'].strftime('%H:%M')} {schedule['timezone']}"
    
    @classmethod
    def get_market_summary(cls) -> Dict:
        """Get summary of all market statuses"""
        now_utc = datetime.now(ZoneInfo('UTC'))
        open_markets = cls.get_open_markets()
        
        summary = {
            'timestamp_utc': now_utc.strftime('%Y-%m-%d %H:%M:%S UTC'),
            'total_markets': len(cls.MARKET_SCHEDULES),
            'open_markets_count': len(open_markets),
            'open_markets': list(open_markets.keys()),
            'markets_status': {}
        }
        
        for market_id, schedule in cls.MARKET_SCHEDULES.items():
            is_open = market_id in open_markets
            summary['markets_status'][market_id] = {
                'name': schedule['name'],
                'is_open': is_open,
                'broker': schedule['broker'],
                'status': 'OPEN' if is_open else 'CLOSED',
                'next_event': cls.get_next_market_open(market_id)
            }
        
        return summary
    
    @classmethod
    def get_active_brokers(cls) -> Set[str]:
        """Get set of active brokers (returns 'capital' when US market is open)."""
        open_markets = cls.get_open_markets()
        brokers = set()
        
        for market_data in open_markets.values():
            brokers.add(market_data['broker'])
        
        return brokers
    
    @classmethod
    def is_us_market_open(cls) -> bool:
        """Convenience method: Check if US market is open"""
        return cls.is_market_open('US')
