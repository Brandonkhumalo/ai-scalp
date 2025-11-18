from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import get_user_model
from django.db import transaction as db_transaction
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .models import Transaction, Trade, AuditLog, KYCRecord, AMLAlert, ModelRegistry
from accounts.models import UserRole
from .permissions import IsAdmin, IsAdminOrComplianceOfficer
from decimal import Decimal
from dateutil import parser

import logging

logger = logging.getLogger(__name__)

User = get_user_model()


class HealthCheckView(APIView):
    """Health check endpoint for deployment monitoring"""
    permission_classes = [AllowAny]
    
    def get(self, request):
        return JsonResponse({
            'status': 'ok',
            'service': 'ZimAI Trader API',
            'timestamp': timezone.now().isoformat()
        }, status=200)


class TransactionListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        transactions = Transaction.objects.filter(user=request.user).order_by('-created_at')
        data = [{
            'id': t.id,
            'type': t.type,
            'amount': float(t.amount),
            'currency': t.currency,
            'payment_method': t.payment_method,
            'reference': t.reference,
            'status': t.status,
            'created_at': t.created_at.isoformat(),
        } for t in transactions]
        return Response(data, status=status.HTTP_200_OK)


class TradeListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .market_data_service import MarketDataService
        from .alpaca_account_service import AlpacaAccountService
        import logging
        logger = logging.getLogger(__name__)
        
        trades = Trade.objects.filter(user=request.user).order_by('-created_at')
        market_service = MarketDataService()
        alpaca_service = AlpacaAccountService()
        
        # Fetch Alpaca closed positions with realized P&L (last 30 days)
        alpaca_closed_positions = {}
        try:
            closed_positions = alpaca_service.get_closed_positions_with_pnl(days_back=30)
            # Create a lookup map by symbol and close time
            for pos in closed_positions:
                symbol = pos.get('symbol')
                close_time = pos.get('close_time')
                if symbol and close_time:
                    key = f"{symbol}_{close_time}"
                    alpaca_closed_positions[key] = pos
            logger.info(f"Fetched {len(closed_positions)} closed positions from Alpaca")
        except Exception as e:
            logger.error(f"Error fetching Alpaca closed positions: {e}")
        
        data = []
        for t in trades:
            # Calculate real-time P&L for open trades
            profit_loss = t.profit_loss
            current_price = None
            
            if t.status == 'open' and t.entry_price:
                try:
                    
                        # Default: Get price from Alpaca (for alpaca_sim broker)
                    snapshot = market_service.get_realtime_snapshot(t.symbol)
                        
                    if snapshot:
                        latest_quote = snapshot.get('latestQuote', {})
                        latest_trade = snapshot.get('latestTrade', {})
                            
                        bid = latest_quote.get('bp')
                        ask = latest_quote.get('ap')
                        trade_price = latest_trade.get('p')
                            
                            # Calculate mid-price ONLY if both bid and ask are valid (> 0)
                        if bid is not None and ask is not None and bid > 0 and ask > 0:
                            current_price = (float(bid) + float(ask)) / 2
                            # Use bid if only bid is valid
                        elif bid is not None and bid > 0:
                            current_price = float(bid)
                            # Use ask if only ask is valid
                        elif ask is not None and ask > 0:
                            current_price = float(ask)
                            # Fallback to latest trade price
                        elif trade_price is not None and trade_price > 0:
                            current_price = float(trade_price)
                    
                    # Calculate P&L if we have current price
                    if current_price and current_price > 0:
                        # Convert Decimal to float for calculation
                        quantity_float = float(t.quantity)
                        entry_price_float = float(t.entry_price)
                        
                        if t.side.lower() == 'buy':
                            profit_loss = (float(current_price) - entry_price_float) * quantity_float
                        else:
                            profit_loss = (entry_price_float - float(current_price)) * quantity_float
                except Exception as e:
                    logger.error(f'Error calculating P&L for trade {t.id} ({t.symbol}): {str(e)}')
            
            # Enrich CLOSED trades with Alpaca's realized P&L if available
            if t.status == 'closed' and t.closed_at and t.broker == 'alpaca_sim':
                # Try to match with Alpaca closed position data
                from datetime import datetime, timedelta
                
                # Try to find matching Alpaca data by symbol and approximate close time
                # (within 5 minutes of database close time)
                for alpaca_key, alpaca_pos in alpaca_closed_positions.items():
                    if alpaca_pos.get('symbol') == t.symbol:
                        try:
                            # Parse times
                            alpaca_close_time = parser.isoparse(alpaca_pos['close_time'])
                            db_close_time = t.closed_at
                            
                            # If times match within 5 minutes, use Alpaca's realized P&L
                            if abs((alpaca_close_time - db_close_time).total_seconds()) < 300:
                                realized_pnl = alpaca_pos.get('realized_pnl')
                                if realized_pnl is not None:
                                    profit_loss = float(realized_pnl)
                                    current_price = alpaca_pos.get('exit_price')
                                    logger.info(f"Enriched trade {t.id} ({t.symbol}) with Alpaca realized P&L: ${profit_loss:.2f}")
                                    break
                        except Exception as e:
                            logger.warning(f"Error matching Alpaca data for trade {t.id}: {e}")
            
            data.append({
                'id': t.id,
                'instrument_type': t.instrument_type,
                'symbol': t.symbol,
                'broker': t.broker,
                'quantity': t.quantity,
                'entry_price': float(t.entry_price),
                'exit_price': float(t.exit_price) if t.exit_price else None,
                'current_price': float(current_price) if current_price else None,
                'side': t.side,
                'status': t.status,
                'profit_loss': float(profit_loss) if profit_loss is not None else None,
                'pnl': float(profit_loss) if profit_loss is not None else None,
                'ai_confidence': t.ai_confidence,
                'ai_signal_type': t.ai_signal_type,
                'created_at': t.created_at.isoformat(),
                'closed_at': t.closed_at.isoformat() if t.closed_at else None,
            })
        
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request):
        instrument_type = request.data.get('instrument_type', 'stock')
        symbol = request.data.get('symbol')
        quantity = request.data.get('quantity')
        entry_price = request.data.get('entry_price')
        side = request.data.get('side', 'buy')

        if not all([symbol, quantity, entry_price]):
            return Response({'error': 'Symbol, quantity, and entry_price are required'}, status=status.HTTP_400_BAD_REQUEST)

        trade = Trade.objects.create(
            user=request.user,
            instrument_type=instrument_type,
            symbol=symbol,
            underlying_asset=request.data.get('underlying_asset'),
            option_type=request.data.get('option_type'),
            strike_price=request.data.get('strike_price'),
            expiration_date=request.data.get('expiration_date'),
            quantity=quantity,
            premium=request.data.get('premium'),
            entry_price=entry_price,
            side=side,
            status='open',
            ai_confidence=request.data.get('ai_confidence'),
            ai_signal_type=request.data.get('ai_signal_type')
        )

        AuditLog.objects.create(
            user=request.user,
            action='TRADE_CREATE',
            resource_type='trade',
            resource_id=str(trade.id),
            details={'symbol': symbol, 'side': side, 'quantity': quantity},
            ip_address=request.META.get('REMOTE_ADDR')
        )

        return Response({
            'id': trade.id,
            'message': 'Trade created successfully'
        }, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name='dispatch')
class TradeDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    def patch(self, request, trade_id):
        from django.db import transaction as db_transaction
        
        try:
            with db_transaction.atomic():
                # Lock the trade row to prevent concurrent updates
                trade = Trade.objects.select_for_update().get(id=trade_id, user=request.user)
                
                # Check if trade is already closed
                if trade.status == 'closed':
                    return Response({
                        'error': 'Trade is already closed'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                exit_price = request.data.get('exit_price')
                status_value = request.data.get('status')
                profit_loss = request.data.get('profit_loss')
                
                if exit_price is not None:
                    trade.exit_price = exit_price
                
                if status_value:
                    trade.status = status_value
                    if status_value == 'closed':
                        trade.closed_at = timezone.now()
                
                if profit_loss is not None:
                    trade.profit_loss = profit_loss
                elif exit_price and trade.entry_price:
                    if trade.side.lower() == 'buy':
                        trade.profit_loss = (float(exit_price) - float(trade.entry_price)) * trade.quantity
                    else:
                        trade.profit_loss = (float(trade.entry_price) - float(exit_price)) * trade.quantity
                
                trade.save()
                
                # Update user balance when trade is closed (only if transitioning to closed)
                if status_value == 'closed' and trade.profit_loss is not None:
                    # Lock user row to prevent concurrent balance updates
                    User = get_user_model()
                    user = User.objects.select_for_update().get(id=request.user.id)
                    
                    # Calculate balance change based on trade type
                    if trade.side.lower() == 'buy':
                        # For BUY trades: Return sale proceeds (qty * exit_price)
                        # We deducted (qty * entry_price) when opening, now we get back (qty * exit_price)
                        balance_change = Decimal(str(trade.quantity)) * Decimal(str(trade.exit_price))
                    else:
                        # For SELL trades: Just add the profit/loss (selling logic is different)
                        balance_change = Decimal(str(trade.profit_loss))
                    
                    # Calculate new balance
                    new_balance = user.usd_balance + balance_change
                    
                    # Prevent negative balance - if balance would go negative, close all trades and apply P&L
                    if new_balance < 0:
                        # Start with the actual negative balance to track the deficit
                        user.usd_balance = new_balance
                        
                        # Auto-close all other open trades at current market price and apply their P&L
                        from .market_data_service import MarketDataService
                        market_service = MarketDataService()
                        open_trades = Trade.objects.filter(user=user, status='open').exclude(id=trade.id)
                        
                        for other_trade in open_trades:
                            try:
                                snapshot = market_service.get_realtime_snapshot(other_trade.symbol)
                                current_price = None
                                
                                if snapshot:
                                    latest_quote = snapshot.get('latestQuote', {})
                                    current_price = latest_quote.get('ap', latest_quote.get('bp'))
                                
                                if current_price:
                                    other_trade.exit_price = current_price
                                    if other_trade.side.lower() == 'buy':
                                        other_trade.profit_loss = (float(current_price) - float(other_trade.entry_price)) * other_trade.quantity
                                    else:
                                        other_trade.profit_loss = (float(other_trade.entry_price) - float(current_price)) * other_trade.quantity
                                    other_trade.status = 'closed'
                                    other_trade.closed_at = timezone.now()
                                    other_trade.save()
                                    
                                    # Note: Broker manages balance - we don't update ZimAI balance
                                    # This is legacy code that no longer applies with broker-managed balances
                                    
                                    Transaction.objects.create(
                                        user=user,
                                        type='trade_pnl',
                                        amount=other_trade.profit_loss,
                                        currency='USD',
                                        reference=f'Trade #{other_trade.id} Auto-Closed (Balance $0)',
                                        status='completed'
                                    )
                            except Exception as e:
                                print(f"Error auto-closing trade {other_trade.id}: {e}")
                        
                        # After all auto-closes, clamp balance at $0 minimum
                        user.usd_balance = max(Decimal('0'), user.usd_balance)
                        user.save()
                    else:
                        user.usd_balance = new_balance
                        
                        # If balance reaches exactly $0 or below, auto-close all remaining open trades
                        if user.usd_balance <= 0:
                            from .market_data_service import MarketDataService
                            market_service = MarketDataService()
                            open_trades = Trade.objects.filter(user=user, status='open')
                            
                            for other_trade in open_trades:
                                try:
                                    snapshot = market_service.get_realtime_snapshot(other_trade.symbol)
                                    current_price = None
                                    
                                    if snapshot:
                                        latest_quote = snapshot.get('latestQuote', {})
                                        current_price = latest_quote.get('ap', latest_quote.get('bp'))
                                    
                                    if current_price:
                                        other_trade.exit_price = current_price
                                        if other_trade.side.lower() == 'buy':
                                            other_trade.profit_loss = (float(current_price) - float(other_trade.entry_price)) * other_trade.quantity
                                        else:
                                            other_trade.profit_loss = (float(other_trade.entry_price) - float(current_price)) * other_trade.quantity
                                        other_trade.status = 'closed'
                                        other_trade.closed_at = timezone.now()
                                        other_trade.save()
                                        
                                        # Note: Broker manages balance - we don't update ZimAI balance
                                        # This is legacy code that no longer applies with broker-managed balances
                                        
                                        Transaction.objects.create(
                                            user=user,
                                            type='trade_pnl',
                                            amount=other_trade.profit_loss,
                                            currency='USD',
                                            reference=f'Trade #{other_trade.id} Auto-Closed (Balance $0)',
                                            status='completed'
                                        )
                                except Exception as e:
                                    print(f"Error auto-closing trade {other_trade.id}: {e}")
                            
                            # After all auto-closes, clamp balance at $0 minimum
                            user.usd_balance = max(Decimal('0'), user.usd_balance)
                        
                        # Save final balance
                        user.save()
                    
                    # Create transaction record with signed amount for the original trade
                    Transaction.objects.create(
                        user=user,
                        type='trade_pnl',
                        amount=trade.profit_loss,
                        currency='USD',
                        reference=f'Trade #{trade.id} {"Profit" if trade.profit_loss >= 0 else "Loss"}',
                        status='completed'
                    )
                
                AuditLog.objects.create(
                    user=request.user,
                    action='TRADE_UPDATE',
                    resource_type='trade',
                    resource_id=str(trade.id),
                    details={'status': trade.status, 'exit_price': str(exit_price) if exit_price else None, 'profit_loss': float(trade.profit_loss) if trade.profit_loss else None},
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                return Response({
                    'id': trade.id,
                    'message': 'Trade updated successfully',
                    'status': trade.status,
                    'profit_loss': float(trade.profit_loss) if trade.profit_loss else None
                }, status=status.HTTP_200_OK)
                
        except Trade.DoesNotExist:
            return Response({'error': 'Trade not found'}, status=status.HTTP_404_NOT_FOUND)


class CheckProfitTakingView(APIView):
    """SCALPING: Close trades at 0.8-1% profit or 0.5% stop-loss (quick in/out)"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        from django.db import transaction as db_transaction
        from .market_data_service import MarketDataService
        
        try:
            with db_transaction.atomic():
                # Get user with lock
                user = User.objects.select_for_update().get(id=request.user.id)
                balance = user.usd_balance
                
                # Get all open trades
                open_trades = Trade.objects.select_for_update().filter(user=user, status='open')
                
                if not open_trades.exists():
                    return Response({
                        'checked': True,
                        'action': 'none',
                        'message': 'No open trades'
                    })
                
                # SCALPING PARAMETERS
                PROFIT_TARGET = Decimal('0.008')  # 0.8% profit target per trade
                STOP_LOSS = Decimal('0.005')  # 0.5% stop-loss per trade
                
                market_service = MarketDataService()
                trades_to_close = []
                
                for trade in open_trades:
                    # Get current market price
                    snapshot = market_service.get_realtime_snapshot(trade.symbol)
                    current_price = None
                    
                    if snapshot:
                        # For stocks, data is at top level
                        latest_quote = snapshot.get('latestQuote', {})
                        current_price = latest_quote.get('ap', latest_quote.get('bp'))
                    
                    if current_price:
                        # Calculate current P&L and % change
                        if trade.side.lower() == 'buy':
                            pnl = (float(current_price) - float(trade.entry_price)) * trade.quantity
                            pct_change = (Decimal(str(current_price)) - Decimal(str(trade.entry_price))) / Decimal(str(trade.entry_price))
                        else:
                            pnl = (float(trade.entry_price) - float(current_price)) * trade.quantity
                            pct_change = (Decimal(str(trade.entry_price)) - Decimal(str(current_price))) / Decimal(str(trade.entry_price))
                        
                        # SCALPING LOGIC: Close if profit target hit OR stop-loss triggered
                        reason = None
                        if pct_change >= PROFIT_TARGET:
                            reason = f'Profit Target ({float(pct_change)*100:.2f}%)'
                            trades_to_close.append({
                                'trade': trade,
                                'current_price': current_price,
                                'pnl': pnl,
                                'reason': reason
                            })
                        elif pct_change <= -STOP_LOSS:
                            reason = f'Stop Loss ({float(pct_change)*100:.2f}%)'
                            trades_to_close.append({
                                'trade': trade,
                                'current_price': current_price,
                                'pnl': pnl,
                                'reason': reason
                            })
                
                if trades_to_close:
                    # Close all trades that hit targets (scalping)
                    closed_count = 0
                    total_realized_profit = Decimal('0')
                    close_details = []
                    
                    for item in trades_to_close:
                        trade = item['trade']
                        current_price = item['current_price']
                        pnl = item['pnl']
                        reason = item['reason']
                        
                        # Close the trade
                        trade.exit_price = current_price
                        trade.profit_loss = pnl
                        trade.status = 'closed'
                        trade.closed_at = timezone.now()
                        trade.save()
                        
                        # Note: Broker manages the account balance - we don't update ZimAI balance
                        # Just track the P&L for statistics
                        total_realized_profit += Decimal(str(pnl))
                        
                        # Create transaction
                        Transaction.objects.create(
                            user=user,
                            type='trade_pnl',
                            amount=pnl,
                            currency='USD',
                            reference=f'Trade #{trade.id} Auto-Closed (Scalping: {reason})',
                            status='completed'
                        )
                        
                        close_details.append({
                            'symbol': trade.symbol,
                            'pnl': float(pnl),
                            'reason': reason
                        })
                        closed_count += 1
                    
                    user.save()
                    
                    return Response({
                        'checked': True,
                        'action': 'scalping_auto_close',
                        'closed_count': closed_count,
                        'total_realized_profit': float(total_realized_profit),
                        'new_balance': float(user.usd_balance),
                        'close_details': close_details,
                        'message': f'SCALPING: Closed {closed_count} trades. Realized P&L: ${total_realized_profit:.2f}'
                    })
                else:
                    return Response({
                        'checked': True,
                        'action': 'none',
                        'open_trades_count': open_trades.count(),
                        'message': 'No trades hit scalping targets (0.8% profit or 0.5% stop-loss)'
                    })
                    
        except Exception as e:
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CloseProfitableTradesView(APIView):
    """Close all profitable Alpaca positions via live API"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        from .alpaca_account_service import AlpacaAccountService
        
        try:
            alpaca_service = AlpacaAccountService()
            
            # Get live Alpaca positions (what the user sees on dashboard)
            positions = alpaca_service.get_positions() or []
            
            if not positions:
                return Response({
                    'success': False,
                    'message': 'No open Alpaca positions found'
                }, status=status.HTTP_200_OK)
            
            # Filter positions with >=1% profit (scalping target)
            profitable_positions = [
                pos for pos in positions 
                if float(pos.get('unrealized_plpc', 0)) >= 0.01  # 1% profit threshold
            ]
            
            if not profitable_positions:
                return Response({
                    'success': False,
                    'message': 'No profitable positions to close. All open positions are currently at a loss.'
                }, status=status.HTTP_200_OK)
            
            # Close each profitable position via Alpaca API
            closed_count = 0
            total_realized_profit = 0
            close_details = []
            failed_closes = []
            
            for pos in profitable_positions:
                symbol = pos.get('symbol')
                qty = abs(float(pos.get('qty', 0)))
                side = pos.get('side')  # 'long' or 'short'
                unrealized_pl = float(pos.get('unrealized_pl', 0))
                avg_entry_price = float(pos.get('avg_entry_price', 0))
                current_price = float(pos.get('current_price', 0))
                
                try:
                    # CRITICAL FIX: Cancel any existing orders for this symbol first
                    # (Alpaca won't let you close positions with pending orders)
                    open_orders = alpaca_service.get_orders(status='open', limit=500)
                    if open_orders:
                        symbol_orders = [o for o in open_orders if o.get('symbol') == symbol]
                        if symbol_orders:
                            logger.info(f"Found {len(symbol_orders)} open orders for {symbol}. Canceling them first...")
                            for order in symbol_orders:
                                order_id = order.get('id')
                                cancel_result = alpaca_service.cancel_order(order_id)
                                logger.info(f"Canceled order {order_id}: {cancel_result}")
                    
                    # Close position via Alpaca API (market order)
                    # For long positions: SELL, for short positions: BUY
                    close_side = 'sell' if side == 'long' else 'buy'
                    
                    logger.info(f"Attempting to close {symbol}: {qty} shares {close_side}")
                    
                    order_result = alpaca_service.place_order(
                        symbol=symbol,
                        qty=qty,
                        side=close_side,
                        order_type='market'
                    )
                    
                    logger.info(f"Alpaca order_result for {symbol}: {order_result}")
                    
                    if order_result and order_result.get('id'):
                        closed_count += 1
                        total_realized_profit += unrealized_pl
                        
                        close_details.append({
                            'symbol': symbol,
                            'side': side,
                            'entry_price': avg_entry_price,
                            'exit_price': current_price,
                            'quantity': qty,
                            'pnl': unrealized_pl,
                            'order_id': order_result.get('id')
                        })
                        
                        # Create database record for tracking (without touching user balance)
                        with db_transaction.atomic():
                            user = User.objects.select_for_update().get(id=request.user.id)
                            
                            # Create trade record
                            Trade.objects.create(
                                user=user,
                                symbol=symbol,
                                instrument_type='stock',
                                side='buy' if side == 'long' else 'sell',
                                quantity=qty,
                                entry_price=avg_entry_price,
                                exit_price=current_price,
                                profit_loss=unrealized_pl,
                                status='closed',
                                closed_at=timezone.now(),
                                broker_deal_id=order_result.get('id')
                            )
                            
                            # Create transaction record
                            Transaction.objects.create(
                                user=user,
                                type='trade_pnl',
                                amount=unrealized_pl,
                                currency='USD',
                                reference=f'Alpaca {symbol} Position Closed (Profit: ${unrealized_pl:.2f})',
                                status='completed'
                            )
                    else:
                        error_msg = f'Alpaca order placement failed. order_result: {order_result}'
                        logger.error(f"{symbol}: {error_msg}")
                        failed_closes.append({
                            'symbol': symbol,
                            'reason': error_msg
                        })
                        
                except Exception as e:
                    logger.exception(f"Exception closing {symbol}")
                    failed_closes.append({
                        'symbol': symbol,
                        'reason': str(e)
                    })
            
            if closed_count > 0:
                message = f'Successfully closed {closed_count} profitable Alpaca position{"s" if closed_count != 1 else ""}. Total profit: ${total_realized_profit:.2f}'
                if failed_closes:
                    message += f' ({len(failed_closes)} failed: {", ".join([f["symbol"] for f in failed_closes])})'
                
                return Response({
                    'success': True,
                    'closed_count': closed_count,
                    'total_realized_profit': total_realized_profit,
                    'close_details': close_details,
                    'failed_closes': failed_closes,
                    'message': message
                })
            else:
                return Response({
                    'success': False,
                    'message': f'Failed to close any positions. Errors: {failed_closes}',
                    'failed_closes': failed_closes
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                    
        except Exception as e:
            return Response({
                'success': False,
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AuditLogListView(APIView):
    permission_classes = [IsAdminOrComplianceOfficer]

    def get(self, request):
        logs = AuditLog.objects.all().order_by('-timestamp')[:100]
        data = [{
            'id': l.id,
            'user_id': l.user.id if l.user else None,
            'action': l.action,
            'resource_type': l.resource_type,
            'resource_id': l.resource_id,
            'details': l.details,
            'timestamp': l.timestamp.isoformat(),
            'ip_address': l.ip_address,
        } for l in logs]
        return Response(data, status=status.HTTP_200_OK)


class KYCListView(APIView):
    permission_classes = [IsAdminOrComplianceOfficer]

    def get(self, request):
        records = KYCRecord.objects.all().order_by('-created_at')
        data = [{
            'id': r.id,
            'user_id': r.user.id,
            'full_name': r.full_name,
            'status': r.status,
            'created_at': r.created_at.isoformat(),
        } for r in records]
        return Response(data, status=status.HTTP_200_OK)


class AMLAlertListView(APIView):
    permission_classes = [IsAdminOrComplianceOfficer]

    def get(self, request):
        alerts = AMLAlert.objects.all().order_by('-created_at')
        data = [{
            'id': a.id,
            'user_id': a.user.id,
            'alert_type': a.alert_type,
            'severity': a.severity,
            'description': a.description,
            'status': a.status,
            'created_at': a.created_at.isoformat(),
            'resolved_at': a.resolved_at.isoformat() if a.resolved_at else None,
        } for a in alerts]
        return Response(data, status=status.HTTP_200_OK)


class ModelRegistryListView(APIView):
    permission_classes = [IsAdminOrComplianceOfficer]

    def get(self, request):
        models = ModelRegistry.objects.all().order_by('-deployed_at')
        data = [{
            'id': m.id,
            'name': m.name,
            'version': m.version,
            'model_type': m.model_type,
            'performance_metrics': m.performance_metrics,
            'validation_results': m.validation_results,
            'deployed_at': m.deployed_at.isoformat(),
            'is_active': m.is_active,
        } for m in models]
        return Response(data, status=status.HTTP_200_OK)


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            'user_id': user.id,
            'email': user.email,
            'full_name': user.full_name,
            'phone': user.phone,
        }, status=status.HTTP_200_OK)


class BalanceHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .alpaca_account_service import AlpacaAccountService
        
        user = request.user
        history = []
        
        # Get all transactions
        transactions = Transaction.objects.filter(user=user).order_by('-created_at')
        for txn in transactions:
            history.append({
                'id': f'txn_{txn.id}',
                'type': txn.type,
                'amount': float(txn.amount),
                'currency': txn.currency,
                'description': f'{txn.type.title()} - {txn.payment_method}',
                'status': txn.status,
                'timestamp': txn.created_at.isoformat(),
                'balance_change': float(txn.amount) if txn.type == 'deposit' else -float(txn.amount),
            })
        
        # Get all closed trades with profit/loss
        trades = Trade.objects.filter(user=user, status='closed').order_by('-closed_at')
        for trade in trades:
            pnl = float(trade.profit_loss or 0)
            history.append({
                'id': f'trade_{trade.id}',
                'type': 'trade',
                'amount': abs(pnl),
                'currency': 'USD',
                'description': f'Trade {trade.side} {trade.symbol} - {"Profit" if pnl > 0 else "Loss"}',
                'status': 'completed',
                'timestamp': trade.closed_at.isoformat() if trade.closed_at else trade.created_at.isoformat(),
                'balance_change': pnl,
                'trade_details': {
                    'symbol': trade.symbol,
                    'side': trade.side,
                    'quantity': float(trade.quantity),
                    'entry_price': float(trade.entry_price),
                    'exit_price': float(trade.exit_price) if trade.exit_price else None,
                }
            })
        
        # Sort all history by timestamp (newest first)
        history.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Get current Alpaca equity for balance calculation
        alpaca_service = AlpacaAccountService()
        current_balance = float(alpaca_service.get_equity() or 100000)
        
        # Calculate running balance
        for item in history:
            item['balance_after'] = current_balance
            current_balance -= item['balance_change']
            item['balance_before'] = current_balance
        
        return Response({
            'current_balance': float(alpaca_service.get_equity() or 100000),
            'history': history
        }, status=status.HTTP_200_OK)


class UserListView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        users = User.objects.all()
        data = []
        for user in users:
            roles = list(user.roles.values_list('role', flat=True))
            data.append({
                'id': user.id,
                'email': user.email,
                'username': user.username,
                'roles': roles,
            })
        return Response(data, status=status.HTTP_200_OK)


class AssignRoleView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request):
        user_id = request.data.get('user_id')
        role = request.data.get('role')

        if not user_id or not role:
            return Response({'error': 'user_id and role are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)

        UserRole.objects.get_or_create(user=user, role=role)

        AuditLog.objects.create(
            user=request.user,
            action='ASSIGN_ROLE',
            resource_type='user_role',
            resource_id=user_id,
            details={'role': role},
            ip_address=request.META.get('REMOTE_ADDR')
        )

        return Response({'message': f'Role {role} assigned successfully'}, status=status.HTTP_200_OK)


class RemoveRoleView(APIView):
    permission_classes = [IsAdmin]

    def post(self, request):
        user_id = request.data.get('user_id')
        role = request.data.get('role')

        if not user_id or not role:
            return Response({'error': 'user_id and role are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(id=user_id)
            user_role = UserRole.objects.get(user=user, role=role)
            user_role.delete()
        except (User.DoesNotExist, UserRole.DoesNotExist):
            return Response({'error': 'User or role not found'}, status=status.HTTP_404_NOT_FOUND)

        AuditLog.objects.create(
            user=request.user,
            action='REMOVE_ROLE',
            resource_type='user_role',
            resource_id=user_id,
            details={'role': role},
            ip_address=request.META.get('REMOTE_ADDR')
        )

        return Response({'message': f'Role {role} removed successfully'}, status=status.HTTP_200_OK)


class GetTradableStocksView(APIView):
    """Get list of tradable stocks from allowlist"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        from .models import TradableInstrument
        
        market = request.GET.get('market')  # Optional filter by US or EU
        
        queryset = TradableInstrument.objects.filter(is_active=True)
        if market:
            queryset = queryset.filter(market=market.upper())
        
        stocks = []
        for instrument in queryset:
            stocks.append({
                'symbol': instrument.symbol,
                'name': instrument.name,
                'market': instrument.market,
                'exchange': instrument.exchange,
                'currency': instrument.currency
            })
        
        return Response({'instruments': stocks}, status=status.HTTP_200_OK)


class ToggleAutonomousAgentView(APIView):
    """Enable/disable the autonomous trading agent for the user"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user = request.user
        enabled = request.data.get('enabled', False)
        
        user.autonomous_trading_enabled = enabled
        user.save()
        
        logger = logging.getLogger(__name__)
        status_text = "enabled" if enabled else "disabled"
        logger.info(f"Autonomous trading {status_text} for user {user.email}")
        
        return Response({
            'message': f'Autonomous trading {status_text}',
            'autonomous_trading_enabled': enabled
        }, status=status.HTTP_200_OK)


class ManualAITradingView(APIView):
    """Manually trigger AI trading for a specific broker"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        from .ai_trading_engine import AITradingEngine
        import logging
        
        logger = logging.getLogger(__name__)
        user = request.user
        broker = request.data.get('broker')
        symbol = request.data.get('symbol')
        instrument_type = request.data.get('instrument_type', 'stock')
        
        valid_brokers = ['alpaca_sim'] #THIS IS WHERE THE MANUAL AI TRADING IS ENABLED
        if broker not in valid_brokers:
            return Response({
                'error': f'Invalid broker. Must be one of: {", ".join(valid_brokers)}'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        if not symbol:
            return Response({
                'error': 'Symbol is required'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            ai_engine = AITradingEngine(user.id, broker)
            result = ai_engine.execute_ai_trade(user, symbol, instrument_type=instrument_type)
            
            if result.get('success'):
                logger.info(f"Manual AI trade executed for {user.email}: {broker} - {symbol}")
                return Response(result, status=status.HTTP_200_OK)
            else:
                return Response(result, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f"Error executing manual AI trade: {str(e)}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AgentStatusView(APIView):
    """Get the current status of the autonomous trading agent"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        from .market_hours_service import MarketHoursService
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"AgentStatusView called - User: {request.user}, Authenticated: {request.user.is_authenticated}")
        
        if not request.user.is_authenticated:
            logger.error("AgentStatusView: User not authenticated")
            return Response({
                'error': 'Authentication required'
            }, status=status.HTTP_401_UNAUTHORIZED)
        
        user = request.user
        market_summary = MarketHoursService.get_market_summary()
        
        logger.info(f"AgentStatusView returning status for user: {user.email}")
        
        return Response({
            'user': {
            'autonomous_trading_enabled': getattr(user, 'autonomous_trading_enabled', False),
            'ai_trading_enabled': getattr(user, 'ai_trading_enabled', False),
            },
            'market_status': market_summary
        }, status=status.HTTP_200_OK)


class AlpacaEquityHistoryView(APIView):
    """Fetch Alpaca equity history for charting"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        from .models import AlpacaEquitySnapshot
        from datetime import timedelta
        from django.utils import timezone
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Get the most recent 500 snapshots (or last 30 days), then reverse for chronological order
            # This ensures we always show the LATEST data, not the oldest
            thirty_days_ago = timezone.now() - timedelta(days=30)
            
            snapshots = list(AlpacaEquitySnapshot.objects.filter(
                user=request.user,
                timestamp__gte=thirty_days_ago  # Only last 30 days
            ).order_by('-timestamp')[:500])  # Get 500 most recent, descending
            
            # Reverse to chronological order for charting
            snapshots.reverse()
            
            data = []
            for snapshot in snapshots:
                data.append({
                    'timestamp': snapshot.timestamp.isoformat(),
                    'equity': float(snapshot.equity),
                    'cash': float(snapshot.cash),
                    'unrealized_pl': float(snapshot.unrealized_pl),
                    'daily_pl': float(getattr(snapshot, 'daily_pl', 0))
                })
            
            return Response({
                'history': data,
                'count': len(data)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error fetching Alpaca equity history: {str(e)}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class AlpacaAccountView(APIView):
    """Fetch live Alpaca account data (balance, buying power, positions) with intelligent caching"""
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        from .alpaca_account_service import AlpacaAccountService
        from .models import AlpacaEquitySnapshot
        from datetime import datetime
        from decimal import Decimal
        import logging
        logger = logging.getLogger(__name__)
        
        try:
            # Initialize Alpaca account service (with caching)
            alpaca_service = AlpacaAccountService()
            
            # Force refresh if requested by query param
            force_refresh = request.query_params.get('force_refresh', 'false').lower() == 'true'
            
            # Get account info (cached for 30 seconds unless force refresh)
            account_info = alpaca_service.get_account_info(force_refresh=force_refresh)
            
            if not account_info:
                return Response({
                    'error': 'Unable to fetch Alpaca account data'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # Get positions (cached for 10 seconds unless force refresh)
            positions = alpaca_service.get_positions(force_refresh=force_refresh)
            
            # Calculate total position value and unrealized P&L
            total_position_value = 0
            total_unrealized_pl = 0
            position_details = []
            for pos in positions:
                market_value = float(pos.get('market_value', 0))
                unrealized_pl = float(pos.get('unrealized_pl', 0))
                total_position_value += market_value
                total_unrealized_pl += unrealized_pl
                
                position_details.append({
                    'symbol': pos.get('symbol'),
                    'qty': float(pos.get('qty', 0)),
                    'avg_entry_price': float(pos.get('avg_entry_price', 0)),
                    'current_price': float(pos.get('current_price', 0)),
                    'market_value': market_value,
                    'unrealized_pl': unrealized_pl,
                    'unrealized_plpc': float(pos.get('unrealized_plpc', 0)),
                    'side': pos.get('side'),
                })
            
            # Save equity snapshot for historical tracking (every 3 minutes max)
            equity = float(account_info.get('equity', 0))
            cash = float(account_info.get('cash', 0))
            last_equity = float(account_info.get('last_equity', equity))  # Yesterday's closing
            
            # Calculate daily P&L (today's equity - yesterday's closing)
            daily_pl = equity - last_equity
            
            # Check if we need to save a snapshot (avoid too frequent saves)
            last_snapshot = AlpacaEquitySnapshot.objects.filter(user=request.user).first()
            should_save_snapshot = True
            if last_snapshot:
                from django.utils import timezone
                time_diff = timezone.now() - last_snapshot.timestamp
                # Save new snapshot if 3+ minutes have passed
                should_save_snapshot = time_diff.total_seconds() >= 180
            
            if should_save_snapshot:
                AlpacaEquitySnapshot.objects.create(
                    user=request.user,
                    equity=Decimal(str(equity)),
                    cash=Decimal(str(cash)),
                    unrealized_pl=Decimal(str(total_unrealized_pl)),
                    daily_pl=Decimal(str(daily_pl))
                )
            
            logger.info(f"Alpaca account data fetched for user {request.user.email}: "
                       f"equity=${equity}, positions={len(positions)}")
            
            return Response({
                'account': {
                    'equity': equity,
                    'cash': cash,
                    'buying_power': float(account_info.get('buying_power', 0)),
                    'portfolio_value': float(account_info.get('portfolio_value', 0)),
                    'pattern_day_trader': account_info.get('pattern_day_trader', False),
                    'daytrade_count': int(account_info.get('daytrade_count', 0)),
                    'last_equity': float(account_info.get('last_equity', 0)),
                    'multiplier': float(account_info.get('multiplier', 1)),
                },
                'positions': {
                    'count': len(positions),
                    'total_value': total_position_value,
                    'details': position_details
                },
                'cached': not force_refresh,
                'timestamp': datetime.now().isoformat()
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error fetching Alpaca account data: {str(e)}")
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PerformanceAnalyticsView(APIView):
    """
    Calculate performance analytics from local database trades
    Shows only trades executed through the ZimAI platform (post-algorithm update)
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        try:
            # Fetch closed trades from local database
            closed_trades = Trade.objects.filter(
                user=request.user,
                closed_at__isnull=False
            ).order_by('-closed_at')
            
            if not closed_trades.exists():
                return Response({
                    'totalTrades': 0,
                    'winningTrades': 0,
                    'losingTrades': 0,
                    'winRate': 0,
                    'totalProfit': 0,
                    'totalLoss': 0,
                    'netPnL': 0,
                    'averageWin': 0,
                    'averageLoss': 0,
                    'profitFactor': 0,
                    'largestWin': 0,
                    'largestLoss': 0,
                    'averageHoldTime': '0h',
                    'roi': 0
                }, status=status.HTTP_200_OK)
            
            # Calculate metrics from local trades
            winning_trades = []
            losing_trades = []
            total_hold_time = 0
            
            for trade in closed_trades:
                pl = float(trade.profit_loss) if trade.profit_loss else 0
                
                if pl > 0:
                    winning_trades.append(pl)
                elif pl < 0:
                    losing_trades.append(abs(pl))
                
                # Calculate hold time
                if trade.created_at and trade.closed_at:
                    hold_time_hours = (trade.closed_at - trade.created_at).total_seconds() / 3600
                    total_hold_time += hold_time_hours
            
            if not winning_trades and not losing_trades:
                return Response({
                    'totalTrades': closed_trades.count(),
                    'winningTrades': 0,
                    'losingTrades': 0,
                    'winRate': 0,
                    'totalProfit': 0,
                    'totalLoss': 0,
                    'netPnL': 0,
                    'averageWin': 0,
                    'averageLoss': 0,
                    'profitFactor': 0,
                    'largestWin': 0,
                    'largestLoss': 0,
                    'averageHoldTime': '0h',
                    'roi': 0
                }, status=status.HTTP_200_OK)
            
            # Calculate performance metrics
            total_profit = sum(winning_trades) if winning_trades else 0
            total_loss = sum(losing_trades) if losing_trades else 0
            net_pnl = total_profit - total_loss
            
            total_trades = len(winning_trades) + len(losing_trades)
            win_rate = (len(winning_trades) / total_trades) * 100 if total_trades > 0 else 0
            
            avg_win = total_profit / len(winning_trades) if winning_trades else 0
            avg_loss = total_loss / len(losing_trades) if losing_trades else 0
            
            profit_factor = total_profit / total_loss if total_loss > 0 else (999 if total_profit > 0 else 0)
            
            largest_win = max(winning_trades) if winning_trades else 0
            largest_loss = max(losing_trades) if losing_trades else 0
            
            # Calculate average hold time
            avg_hold_hours = total_hold_time / total_trades if total_trades > 0 else 0
            
            if avg_hold_hours < 1:
                avg_hold_time_str = f"{int(avg_hold_hours * 60)}m"
            elif avg_hold_hours < 24:
                avg_hold_time_str = f"{avg_hold_hours:.1f}h"
            else:
                avg_hold_time_str = f"{(avg_hold_hours / 24):.1f}d"
            
            # Calculate ROI based on initial capital
            from .alpaca_account_service import AlpacaAccountService
            alpaca_service = AlpacaAccountService()
            account_info = alpaca_service.get_account_info()
            current_equity = float(account_info.get('equity', 100000)) if account_info else 100000
            initial_capital = current_equity - net_pnl
            roi = (net_pnl / initial_capital) * 100 if initial_capital > 0 else 0
            
            return Response({
                'totalTrades': total_trades,
                'winningTrades': len(winning_trades),
                'losingTrades': len(losing_trades),
                'winRate': round(win_rate, 2),
                'totalProfit': round(total_profit, 2),
                'totalLoss': round(total_loss, 2),
                'netPnL': round(net_pnl, 2),
                'averageWin': round(avg_win, 2),
                'averageLoss': round(avg_loss, 2),
                'profitFactor': round(profit_factor, 2) if profit_factor < 999 else 999,
                'largestWin': round(largest_win, 2),
                'largestLoss': round(largest_loss, 2),
                'averageHoldTime': avg_hold_time_str,
                'roi': round(roi, 2)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Error calculating performance analytics: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            return Response({
                'error': str(e),
                'totalTrades': 0,
                'winningTrades': 0,
                'losingTrades': 0,
                'winRate': 0,
                'totalProfit': 0,
                'totalLoss': 0,
                'netPnL': 0,
                'averageWin': 0,
                'averageLoss': 0,
                'profitFactor': 0,
                'largestWin': 0,
                'largestLoss': 0,
                'averageHoldTime': '0h',
                'roi': 0
            }, status=status.HTTP_200_OK)

from django.forms.models import model_to_dict

from .models import (
    Trade, AuditLog, AMLAlert, ModelRegistry,
    TradableInstrument, BrokerAccountSummary,
    AlpacaEquitySnapshot
)

def get_all_data(request):
    """
    Return ALL database records except Transaction and KYCRecord.
    """
    
    data = {
        "trades": list(Trade.objects.all().values()),
        "audit_logs": list(AuditLog.objects.all().values()),
        "aml_alerts": list(AMLAlert.objects.all().values()),
        "model_registry": list(ModelRegistry.objects.all().values()),
        "tradable_instruments": list(TradableInstrument.objects.all().values()),
        "broker_summaries": list(BrokerAccountSummary.objects.all().values()),
        "alpaca_snapshots": list(AlpacaEquitySnapshot.objects.all().values()),
    }

    return JsonResponse(
        {
            "success": True,
            "count": {k: len(v) for k, v in data.items()},
            "data": data
        },
        safe=False,
        json_dumps_params={"indent": 2}
    )

from rest_framework.decorators import api_view
from datetime import datetime
import datetime as dt
from rest_framework.decorators import api_view, permission_classes
@api_view(['DELETE'])
@permission_classes([AllowAny])
def delete_old_trades_and_show_wins(request):
    """
    Permanently delete all trades created before 11 November 2025,
    then return all remaining winning trades (profit_loss > 0).
    """

    # Target cutoff timestamp
    cutoff_date = datetime(2025, 11, 11, tzinfo=dt.timezone.utc)

    # Count trades to delete
    to_delete_count = Trade.objects.filter(created_at__lt=cutoff_date).count()

    # Permanently delete old trades
    Trade.objects.filter(created_at__lt=cutoff_date).delete()

    # Remaining winning trades
    winning_trades = list(
        Trade.objects.filter(profit_loss__gt=0).values()
    )

    return Response(
        {
            "success": True,
            "deleted_trades": to_delete_count,
            "remaining_winning_trades_count": len(winning_trades),
            "winning_trades": winning_trades,
        }
    )