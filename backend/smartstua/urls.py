"""
Smart-Stua Django URL Configuration
Routes all API endpoints under /api/
"""

from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('monitoring.urls')),
]
