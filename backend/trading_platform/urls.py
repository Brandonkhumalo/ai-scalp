"""
URL configuration for trading_platform project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.http import FileResponse
from django.views.generic import View
from api.views import HealthCheckView
import os

class ReactAppView(View):
    """Serve React index.html for SPA routes"""
    def get(self, request, *args, **kwargs):
        index_path = os.path.join(settings.REACT_BUILD_DIR, 'index.html')
        if os.path.exists(index_path):
            return FileResponse(open(index_path, 'rb'), content_type='text/html')
        return FileResponse(open(os.path.join(settings.BASE_DIR.parent, 'index.html'), 'rb'), content_type='text/html')

urlpatterns = [
    path('api/health/', HealthCheckView.as_view(), name='health-check'),
    path('admin/', admin.site.urls),
    path('api/auth/', include('accounts.urls')),
    path('api/', include('api.urls')),
]

# Serve static assets - CRITICAL: Must be outside DEBUG guard for production
from django.views.static import serve
urlpatterns.append(
    re_path(r'^assets/(?P<path>.*)$', serve, {
        'document_root': os.path.join(settings.REACT_BUILD_DIR, 'assets'),
    })
)

# Serve React app for root and all other routes (SPA catch-all)
urlpatterns.append(
    re_path(r'^.*$', ReactAppView.as_view(), name='react-app')
)
