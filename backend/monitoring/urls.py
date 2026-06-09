"""
URL routing for the monitoring app.
All endpoints are prefixed with /api/ from the root urlconf.
"""

from django.urls import path
from . import views

urlpatterns = [
    # ── DFD 1.0: Capture Sensor Data ─────────────────────────────────────────
    path('readings/', views.receive_reading, name='receive-reading'),

    # ── Device Management ────────────────────────────────────────────────────
    path('devices/', views.device_list, name='device-list'),
    path('devices/<int:node_id>/readings/', views.device_readings, name='device-readings'),
    path('devices/<int:node_id>/latest/', views.device_latest, name='device-latest'),
    path('devices/<str:node_id>/command/', views.device_command, name='device-command'),
    path('devices/<int:node_id>/dryer/', views.dryer_override, name='dryer-override'),

    # ── Dashboard ─────────────────────────────────────────────────────────────
    path('dashboard/summary/', views.dashboard_summary, name='dashboard-summary'),

    # ── Alerts ───────────────────────────────────────────────────────────────
    path('alerts/', views.alert_list, name='alert-list'),
    path('alerts/<int:alert_id>/acknowledge/', views.alert_acknowledge, name='alert-acknowledge'),

    # ── Thresholds (UC3) ─────────────────────────────────────────────────────
    path('thresholds/<str:node_identifier>/', views.threshold_detail, name='threshold-detail'),

    # ── Auth (UC4) ────────────────────────────────────────────────────────────
    path('auth/login/', views.login_view, name='login'),
    path('auth/register/', views.register_view, name='register'),
]
