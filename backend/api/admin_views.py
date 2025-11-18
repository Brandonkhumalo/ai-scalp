from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.contrib.auth import get_user_model
from django.db.models import Sum, Q, Count
from django.utils import timezone
from django.db import transaction
from decimal import Decimal
from .models import Trade, AuditLog
from accounts.models import UserRole
import logging

User = get_user_model()
logger = logging.getLogger(__name__)


def is_admin(user):
    return UserRole.objects.filter(user=user, role='admin').exists()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_all_users(request):
    if not is_admin(request.user):
        return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
    
    users = User.objects.all().order_by('-created_at')
    
    users_data = []
    for user in users:
        open_trades = Trade.objects.filter(user=user, status='open').count()
        total_pnl = Trade.objects.filter(user=user, status='closed').aggregate(
            total=Sum('profit_loss')
        )['total'] or Decimal('0')
        
        is_currently_trading = open_trades > 0
        
        users_data.append({
            'id': user.id,
            'email': user.email,
            'full_name': user.full_name,
            'phone': user.phone,
            'usd_balance': float(user.usd_balance),
            'zwl_balance': float(user.zwl_balance),
            'approval_status': user.approval_status,
            'ai_trading_enabled': user.ai_trading_enabled,
            'is_currently_trading': is_currently_trading,
            'open_trades_count': open_trades,
            'total_pnl': float(total_pnl),
            'created_at': user.created_at.isoformat(),
            'approved_at': user.approved_at.isoformat() if user.approved_at else None,
            'approved_by_email': user.approved_by.email if user.approved_by else None,
        })
    
    return Response({
        'success': True,
        'users': users_data,
        'total_count': len(users_data)
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def approve_user(request, user_id):
    if not is_admin(request.user):
        return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    
    with transaction.atomic():
        user.approval_status = 'approved'
        user.approved_by = request.user
        user.approved_at = timezone.now()
        user.save()
        
        AuditLog.objects.create(
            user=request.user,
            action='user_approved',
            resource_type='user',
            resource_id=str(user.id),
            details={
                'approved_user_email': user.email,
                'admin_email': request.user.email
            },
            ip_address=request.META.get('REMOTE_ADDR')
        )
    
    logger.info(f'Admin {request.user.email} approved user {user.email}')
    
    return Response({
        'success': True,
        'message': f'User {user.email} approved successfully'
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reject_user(request, user_id):
    if not is_admin(request.user):
        return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
    
    with transaction.atomic():
        user.approval_status = 'rejected'
        user.approved_by = request.user
        user.approved_at = timezone.now()
        user.save()
        
        AuditLog.objects.create(
            user=request.user,
            action='user_rejected',
            resource_type='user',
            resource_id=str(user.id),
            details={
                'rejected_user_email': user.email,
                'admin_email': request.user.email
            },
            ip_address=request.META.get('REMOTE_ADDR')
        )
    
    logger.info(f'Admin {request.user.email} rejected user {user.email}')
    
    return Response({
        'success': True,
        'message': f'User {user.email} rejected'
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_realtime_trading_stats(request):
    if not is_admin(request.user):
        return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
    
    active_traders = User.objects.filter(
        trades__status='open'
    ).distinct()
    
    active_traders_data = []
    for trader in active_traders:
        open_trades = Trade.objects.filter(user=trader, status='open')
        total_pnl_today = Trade.objects.filter(
            user=trader,
            status='closed',
            closed_at__gte=timezone.now().date()
        ).aggregate(total=Sum('profit_loss'))['total'] or Decimal('0')
        
        total_pnl_all_time = Trade.objects.filter(
            user=trader,
            status='closed'
        ).aggregate(total=Sum('profit_loss'))['total'] or Decimal('0')
        
        trades_data = []
        for trade in open_trades:
            trades_data.append({
                'symbol': trade.symbol,
                'side': trade.side,
                'quantity': float(trade.quantity),
                'entry_price': float(trade.entry_price),
                'ai_confidence': trade.ai_confidence,
                'created_at': trade.created_at.isoformat()
            })
        
        active_traders_data.append({
            'user_id': trader.id,
            'email': trader.email,
            'full_name': trader.full_name,
            'usd_balance': float(trader.usd_balance),
            'open_trades': trades_data,
            'pnl_today': float(total_pnl_today),
            'pnl_all_time': float(total_pnl_all_time),
            'ai_trading_enabled': trader.ai_trading_enabled
        })
    
    total_open_trades = Trade.objects.filter(status='open').count()
    total_pnl_today = Trade.objects.filter(
        status='closed',
        closed_at__gte=timezone.now().date()
    ).aggregate(total=Sum('profit_loss'))['total'] or Decimal('0')
    
    return Response({
        'success': True,
        'active_traders': active_traders_data,
        'summary': {
            'total_active_traders': len(active_traders_data),
            'total_open_trades': total_open_trades,
            'total_pnl_today': float(total_pnl_today)
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_platform_overview(request):
    if not is_admin(request.user):
        return Response({'error': 'Admin access required'}, status=status.HTTP_403_FORBIDDEN)
    
    total_users = User.objects.count()
    pending_approvals = User.objects.filter(approval_status='pending').count()
    approved_users = User.objects.filter(approval_status='approved').count()
    rejected_users = User.objects.filter(approval_status='rejected').count()
    
    total_trades = Trade.objects.count()
    open_trades = Trade.objects.filter(status='open').count()
    closed_trades = Trade.objects.filter(status='closed').count()
    
    total_pnl = Trade.objects.filter(status='closed').aggregate(
        total=Sum('profit_loss')
    )['total'] or Decimal('0')
    
    ai_enabled_users = User.objects.filter(ai_trading_enabled=True).count()
    
    return Response({
        'success': True,
        'overview': {
            'total_users': total_users,
            'pending_approvals': pending_approvals,
            'approved_users': approved_users,
            'rejected_users': rejected_users,
            'total_trades': total_trades,
            'open_trades': open_trades,
            'closed_trades': closed_trades,
            'total_platform_pnl': float(total_pnl),
            'ai_enabled_users': ai_enabled_users
        }
    })
