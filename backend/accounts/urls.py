from django.urls import path
from .views import (
    RegisterView, LoginView, LogoutView, RefreshTokenView, MeView,
    ToggleAITradingView, CapitalCredentialsView
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('refresh/', RefreshTokenView.as_view(), name='refresh_token'),
    path('me/', MeView.as_view(), name='me'),
    path('toggle-ai-trading/', ToggleAITradingView.as_view(), name='toggle_ai_trading'),
    path('capital-credentials/', CapitalCredentialsView.as_view(), name='capital_credentials'),
]
