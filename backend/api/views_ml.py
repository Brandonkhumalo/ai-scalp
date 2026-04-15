from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny
from .models import Trade
from .ml_training_service import MLTradingModel, FEATURE_NAMES
from .trade_data_quality_service import TradeDataQualityAuditor
from .walkforward_service import ExecutionCostModel, WalkForwardConfig, WalkForwardValidator
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
                metrics['expected_features'] = ml_model.expected_features
                metrics['feature_names'] = FEATURE_NAMES
                metrics['model_version_expected'] = ml_model.model_version
                saved_count = len(metrics.get('feature_importances', {}))
                metrics['saved_feature_count'] = saved_count
                metrics['feature_schema_match'] = saved_count in (0, ml_model.expected_features)
                return Response(metrics, status=status.HTTP_200_OK)
            
            elif action == 'predict':
                # Make a prediction on new features
                features = request.data.get('features')
                
                if not features or len(features) != ml_model.expected_features:
                    return Response({
                        'error': (
                            f'Invalid features. Expected array of '
                            f'{ml_model.expected_features} values'
                        )
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                prediction = ml_model.predict(features)
                return Response(prediction, status=status.HTTP_200_OK)

            elif action == 'auditDataQuality':
                user_id = request.data.get('user_id')
                qs = Trade.objects.all().order_by('created_at')
                if user_id:
                    qs = qs.filter(user_id=user_id)
                auditor = TradeDataQualityAuditor()
                report = auditor.audit(qs)
                return Response({
                    'success': True,
                    'report': report.__dict__,
                }, status=status.HTTP_200_OK)

            elif action == 'walkForwardValidate':
                user_id = request.data.get('user_id')
                qs = Trade.objects.filter(status='closed').order_by('closed_at', 'created_at')
                if user_id:
                    qs = qs.filter(user_id=user_id)

                cost_model = ExecutionCostModel(
                    spread_bps=request.data.get('spread_bps', 2.0),
                    slippage_bps=request.data.get('slippage_bps', 3.0),
                    commission_per_share=request.data.get('commission_per_share', 0.0035),
                    per_trade_fee=request.data.get('per_trade_fee', 0.00),
                )
                config = WalkForwardConfig(
                    min_train_trades=request.data.get('min_train_trades', 40),
                    test_size=request.data.get('test_size', 20),
                    step_size=request.data.get('step_size', 20),
                    min_test_trades=request.data.get('min_test_trades', 8),
                    confidence_candidates=request.data.get('confidence_candidates'),
                )

                validator = WalkForwardValidator(cost_model=cost_model)
                result = validator.evaluate(qs, config=config)
                http_status = status.HTTP_200_OK if result.get('success') else status.HTTP_400_BAD_REQUEST
                return Response(result, status=http_status)
            
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
                    'error': (
                        'Invalid action. Use: train, getMetrics, predict, '
                        'autoRetrain, auditDataQuality, or walkForwardValidate'
                    )
                }, status=status.HTTP_400_BAD_REQUEST)
                
        except Exception as e:
            logger.error(f'ML model error: {str(e)}')
            return Response({
                'error': str(e)
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
