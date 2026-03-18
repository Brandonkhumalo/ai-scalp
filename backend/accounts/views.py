from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password, check_password
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from .authentication import JWTAuthentication
from .models import BlacklistedToken, UserRole
from .serializers import UserSerializer
import jwt
from django.conf import settings
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

User = get_user_model()


class RegisterView(APIView):
    permission_classes = [AllowAny]

    @method_decorator(ratelimit(key='ip', rate='5/m', method='POST', block=True))
    def post(self, request):
        email = request.data.get('email', '').lower().strip()
        password = request.data.get('password')
        username = request.data.get('username', email.split('@')[0])
        full_name = request.data.get('full_name', '')
        phone = request.data.get('phone', '')

        if not email or not password:
            return Response({'error': 'Email and password are required'}, status=status.HTTP_400_BAD_REQUEST)

        if User.objects.filter(email=email).exists():
            return Response({'error': 'Email already exists'}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create(
            email=email,
            username=username,
            password=make_password(password),
            full_name=full_name,
            phone=phone
        )

        UserRole.objects.create(user=user, role='user')  # type: ignore

        payload = {
            'id': user.id,
            'email': user.email,
            'username': user.username
        }

        access_token = JWTAuthentication.generate_token(payload=payload)
        refresh_token = JWTAuthentication.generate_refresh_token(payload=payload)

        return Response({
            'accessToken': access_token,
            'refreshToken': refresh_token,
            'user': UserSerializer(user).data,
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    @method_decorator(ratelimit(key='ip', rate='5/m', method='POST', block=True))
    def post(self, request):
        email = request.data.get('email', '').lower().strip()
        password = request.data.get('password')

        if not email or not password:
            return Response({'error': 'Email and password are required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

        if not check_password(password, user.password):
            return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

        payload = {
            'id': user.id,
            'email': user.email,
            'username': user.username
        }

        access_token = JWTAuthentication.generate_token(payload=payload)
        refresh_token = JWTAuthentication.generate_refresh_token(payload=payload)

        return Response({
            'accessToken': access_token,
            'refreshToken': refresh_token,
            'user': UserSerializer(user).data,
        }, status=status.HTTP_200_OK)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        token = request.auth
        if token:
            from .authentication import mark_token_blacklisted
            mark_token_blacklisted(token)
        return Response({'message': 'Logged out successfully'}, status=status.HTTP_200_OK)


class RefreshTokenView(APIView):
    permission_classes = [AllowAny]

    @method_decorator(ratelimit(key='ip', rate='10/m', method='POST', block=True))
    def post(self, request):
        refresh_token = request.data.get('refreshToken')

        if not refresh_token:
            return Response({'error': 'Refresh token is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payload = jwt.decode(refresh_token, settings.SECRET_KEY, algorithms=['HS256'])

            if payload.get('type') != 'refresh_token':
                return Response({'error': 'Invalid token type'}, status=status.HTTP_400_BAD_REQUEST)

            user_id = payload.get('id')
            user = User.objects.get(id=user_id)

            new_payload = {
                'id': user.id,
                'email': user.email,
                'username': user.username
            }

            access_token = JWTAuthentication.generate_token(payload=new_payload)

            return Response({
                'accessToken': access_token,
            }, status=status.HTTP_200_OK)

        except (jwt.ExpiredSignatureError, jwt.DecodeError, User.DoesNotExist):
            return Response({'error': 'Invalid or expired refresh token'}, status=status.HTTP_401_UNAUTHORIZED)


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_data = UserSerializer(request.user).data
        return Response({
            'user': user_data,
            'roles': user_data.get('roles', []),
        }, status=status.HTTP_200_OK)



class ToggleAITradingView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from django.db import transaction as db_transaction
        import logging

        logger = logging.getLogger(__name__)
        user = request.user
        enabled = request.data.get('enabled', False)

        logger.info(f"Toggle AI endpoint: user={user.email}, enabled={enabled}")

        if not enabled and user.ai_trading_enabled:
            try:
                from api.models import Trade
                from api.services import alpaca_service
                from django.utils import timezone
                from decimal import Decimal
                import time
                
                logger.info(f"Stopping AI for {user.email}: Canceling orders and closing positions")
                alpaca_service.cancel_all_orders()
                
                positions = alpaca_service.get_positions() or []
                closed_symbols = []
                
                if positions:
                    for pos in positions:
                        symbol = pos.get('symbol')
                        qty = abs(float(pos.get('qty', 0)))
                        side = pos.get('side')
                        close_side = 'sell' if side == 'long' else 'buy'
                        is_crypto = '/' in symbol or (symbol.endswith('USD') and len(symbol) <= 7)
                        tif = 'gtc' if is_crypto else 'day'
                        
                        try:
                            alpaca_service.place_order(
                                symbol=symbol,
                                qty=qty,
                                side=close_side,
                                order_type='market',
                                time_in_force=tif
                            )
                            logger.info(f"Closed {symbol}: {side} {qty} shares")
                            closed_symbols.append(symbol)
                        except Exception as e:
                            logger.error(f"Error closing {symbol}: {str(e)}")
                    
                    # Wait 3 seconds for fills to process
                    if closed_symbols:
                        logger.info("Waiting 3 seconds for fills to process...")
                        time.sleep(3)
                        
                        # Fetch account activities to get actual fill prices
                        try:
                            activities = alpaca_service.get_account_activities(activity_types='FILL', limit=100)
                            
                            # Process each closed symbol
                            for symbol in closed_symbols:
                                # Find matching fill activity (most recent)
                                matching_fill = None
                                for activity in activities:
                                    if activity.get('symbol') == symbol and activity.get('side') in ['sell', 'buy']:
                                        matching_fill = activity
                                        break
                                
                                # Update database Trade records
                                open_trades = Trade.objects.filter(
                                    user=user,
                                    broker='alpaca_sim',
                                    symbol=symbol,
                                    status='open'
                                )
                                
                                for trade in open_trades:
                                    if matching_fill:
                                        exit_price = Decimal(str(matching_fill.get('price', trade.entry_price)))
                                        qty = Decimal(str(matching_fill.get('qty', trade.quantity)))
                                        
                                        # Calculate accurate P/L
                                        if trade.side == 'BUY':
                                            profit_loss = (exit_price - trade.entry_price) * qty
                                        else:
                                            profit_loss = (trade.entry_price - exit_price) * qty
                                        
                                        trade.exit_price = exit_price
                                        trade.profit_loss = profit_loss
                                        logger.info(f"Updated {symbol}: exit=${exit_price}, P/L=${profit_loss}")
                                    else:
                                        # No fill found - use neutral close
                                        trade.exit_price = trade.entry_price
                                        trade.profit_loss = Decimal('0.00')
                                        logger.warning(f"No fill found for {symbol}, using neutral close")
                                    
                                    trade.status = 'closed'
                                    trade.closed_at = timezone.now()
                                    trade.save()
                                    
                        except Exception as e:
                            logger.error(f"Error updating database with fill prices: {str(e)}")
                            # Fallback: close with neutral P/L
                            for symbol in closed_symbols:
                                fallback_trades = Trade.objects.filter(
                                    user=user,
                                    broker='alpaca_sim',
                                    symbol=symbol,
                                    status='open'
                                )
                                for trade in fallback_trades:
                                    trade.status = 'closed'
                                    trade.exit_price = trade.entry_price
                                    trade.profit_loss = Decimal('0.00')
                                    trade.closed_at = timezone.now()
                                    trade.save()
                            
            except Exception as e:
                logger.error(f"Error stopping AI: {str(e)}")
        
        with db_transaction.atomic():
            User = get_user_model()
            user = User.objects.select_for_update().get(id=user.id)
            user.ai_trading_enabled = enabled
            user.save()
        
        return Response({
            'ai_trading_enabled': user.ai_trading_enabled,
            'message': f'AI trading {"enabled" if enabled else "disabled"} successfully'
        }, status=status.HTTP_200_OK)
