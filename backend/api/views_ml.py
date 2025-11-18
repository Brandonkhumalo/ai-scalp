from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from .models import Trade
from .ml_training_service import MLTradingModel
import logging

logger = logging.getLogger(__name__)


class MLModelView(APIView):
    """
    API for ML model training and management
    """
    permission_classes = [AllowAny]
    
    def post(self, request):
        """Handle ML model operations"""
        try:
            action = request.data.get('action')
            ml_model = MLTradingModel()
            
            if action == 'train':
                # Get all closed trades for training
                trades = Trade.objects.filter(status='closed').order_by('created_at')
                
                if not trades.exists():
                    return Response({
                        'success': False,
                        'error': 'No closed trades available for training'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Train the model
                result = ml_model.train(list(trades))
                
                return Response(result, status=status.HTTP_200_OK)
            
            elif action == 'getMetrics':
                # Get model performance metrics
                metrics = ml_model.get_metrics()
                return Response(metrics, status=status.HTTP_200_OK)
            
            elif action == 'predict':
                # Make a prediction on new features
                features = request.data.get('features')
                
                if not features or len(features) != 10:
                    return Response({
                        'error': 'Invalid features. Expected array of 10 values'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                prediction = ml_model.predict(features)
                return Response(prediction, status=status.HTTP_200_OK)
            
            elif action == 'autoRetrain':
                # Check if retraining is needed and execute if necessary
                trades = Trade.objects.filter(status='closed').order_by('created_at')
                
                if not trades.exists():
                    return Response({
                        'success': False,
                        'message': 'No trades available for retraining'
                    }, status=status.HTTP_200_OK)
                
                # Get last training time from metrics
                metrics = ml_model.get_metrics()
                last_training = None
                if 'timestamp' in metrics:
                    from datetime import datetime
                    last_training = datetime.fromisoformat(metrics['timestamp'])
                
                # Check if retraining is needed
                new_trades_count = trades.filter(
                    created_at__gt=last_training
                ).count() if last_training else trades.count()
                
                if ml_model.should_retrain(last_training, new_trades_count):
                    result = ml_model.train(list(trades))
                    return Response({
                        'success': True,
                        'retrained': True,
                        'metrics': result
                    }, status=status.HTTP_200_OK)
                else:
                    return Response({
                        'success': True,
                        'retrained': False,
                        'message': 'Model is up to date',
                        'metrics': metrics
                    }, status=status.HTTP_200_OK)
            
            else:
                return Response({
                    'error': 'Invalid action. Use: train, getMetrics, predict, or autoRetrain'
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f'ML model error: {str(e)}')
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
