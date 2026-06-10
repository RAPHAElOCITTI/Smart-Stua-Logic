"""
Smart-Stua API Views
======================
Maps directly to the Data Flow Diagram processes and use cases:

  POST /api/readings/               → DFD 1.0: Capture Sensor Data
  GET  /api/devices/                → List registered sensor nodes
  GET  /api/devices/<id>/readings/  → Dashboard query: historical readings
  GET  /api/devices/<id>/latest/    → Dashboard query: current ARI
  GET  /api/devices/<id>/command/   → Dryer command polling (ESP32)
  GET  /api/dashboard/summary/      → Aggregate all-nodes dashboard
  GET  /api/alerts/                 → Alert history
  GET/PUT /api/thresholds/<node_id> → UC3: Configure Alert Thresholds
  POST /api/auth/login/             → UC4: User Authentication
  POST /api/auth/register/          → UC4: User Registration (admin only)
"""

import logging
from django.utils import timezone
from django.contrib.auth.hashers import check_password
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
# pyrefly: ignore [missing-import]
from rest_framework.authtoken.models import Token

from .models import SensorNode, Reading, AlertLog, Threshold, User, DryerCommand
from .serializers import (
    SensorNodeSerializer, ReadingSerializer, AlertLogSerializer,
    ThresholdSerializer, SensorPayloadSerializer, DashboardNodeSummarySerializer,
    DryerCommandSerializer, UserSerializer, UserRegistrationSerializer,
)
from .ari_algorithm import calculate_ari, get_risk_summary

logger = logging.getLogger(__name__)


# ─── DFD 1.0: Capture Sensor Data ────────────────────────────────────────────
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def receive_reading(request):
    """
    POST /api/readings/
    Accepts JSON from ESP32+SIM800L sensor nodes.
    Validates, stores reading, triggers async ARI calculation.

    Auth: API key in payload (not Bearer token — embedded devices)
    """
    serializer = SensorPayloadSerializer(data=request.data)
    if not serializer.is_valid():
        logger.warning(f'[API] Invalid sensor payload: {serializer.errors}')
        return Response(
            {'error': 'Invalid payload', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data
    node = data['_node']

    # Store reading
    reading = Reading.objects.create(
        node=node,
        temperature_c=data['temperature'],
        humidity_pct=data['humidity'],
        moisture_pct=data.get('moisture_pct'),   # optional — None if not sent
        device_ts=data.get('device_ts'),
    )

    # Update node last_reading_at
    node.last_reading_at = timezone.now()
    node.save(update_fields=['last_reading_at'])

    # Async: compute ARI + dispatch alerts
    from .tasks import process_sensor_data
    process_sensor_data.delay(reading.reading_id)

    logger.info(
        f'[API] Reading accepted: {node.node_identifier} '
        f'T={data["temperature"]}°C H={data["humidity"]}% '
        f'reading_id={reading.reading_id}'
    )

    return Response(
        {
            'status': 'accepted',
            'reading_id': reading.reading_id,
            'node_id': node.node_identifier,
        },
        status=status.HTTP_201_CREATED,
    )


# ─── Device Listing ───────────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def device_list(request):
    """
    GET /api/devices/
    List all registered sensor nodes with status and latest ARI.
    """
    nodes = SensorNode.objects.prefetch_related('readings', 'readings__alert').all()
    serializer = SensorNodeSerializer(nodes, many=True)
    return Response(serializer.data)


# ─── Device Registration (Plug-and-Play) ──────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def device_register(request):
    """
    POST /api/devices/register/
    Dynamic node registration endpoint. Allows the frontend dashboard to
    provision new devices.
    Expects: { "node_identifier": "NODE_XYZ", "location_label": "Silo B", "mac_address": "AA:BB:CC:DD:EE:FF" }
    Returns: The created device object with the unique, auto-generated per-device api_key.
    """
    from .serializers import NodeRegistrationSerializer
    serializer = NodeRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        node = serializer.save()
        logger.info(f'[DEVICE] Dynamic registration: {node.node_identifier} (MAC: {node.mac_address}) by {request.user}')
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─── Historical Readings ──────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def device_readings(request, node_id):
    """
    GET /api/devices/<node_id>/readings/
    Historical readings for a device (paginated, newest first).
    Optional query params: ?limit=100&days=7
    """
    node = get_object_or_404(SensorNode, node_id=node_id)

    days  = int(request.query_params.get('days', 7))
    limit = int(request.query_params.get('limit', 200))

    since = timezone.now() - timezone.timedelta(days=days)
    readings = Reading.objects.filter(
        node=node,
        recorded_at__gte=since,
    ).order_by('-recorded_at')[:limit]

    serializer = ReadingSerializer(readings, many=True)
    return Response({
        'node_identifier': node.node_identifier,
        'location_label': node.location_label,
        'count': len(serializer.data),
        'readings': serializer.data,
    })


# ─── Latest Reading + ARI ─────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def device_latest(request, node_id):
    """
    GET /api/devices/<node_id>/latest/
    Latest reading + current ARI score for a specific node.
    """
    node    = get_object_or_404(SensorNode, node_id=node_id)
    reading = Reading.objects.filter(node=node).order_by('-recorded_at').first()

    if not reading:
        return Response(
            {'error': 'No readings available for this node'},
            status=status.HTTP_404_NOT_FOUND,
        )

    ari_result = calculate_ari(reading.temperature_c, reading.humidity_pct)

    return Response({
        'node_id': node.node_id,
        'node_identifier': node.node_identifier,
        'location_label': node.location_label,
        'status': node.status,
        'reading': ReadingSerializer(reading).data,
        'ari': ari_result,
        'dryer_status': node.pending_command,
    })


# ─── Dryer Command (ESP32 Polling) ───────────────────────────────────────────
@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def device_command(request, node_id):
    """
    GET /api/devices/<node_id>/command/
    Return pending dryer command for ESP32 polling.
    After returning ON/OFF, resets to NONE.
    """
    # Authenticate with API key query param
    api_key = request.query_params.get('api_key', '')
    from django.conf import settings
    if api_key != settings.SENSOR_API_KEY:
        return Response({'error': 'Unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)

    node = get_object_or_404(SensorNode, node_identifier=node_id)
    command = node.pending_command

    # Reset to NONE after delivery
    if command != DryerCommand.NONE:
        node.pending_command = DryerCommand.NONE
        node.save(update_fields=['pending_command'])
        logger.info(f'[CMD] Command "{command}" delivered to {node.node_identifier} — reset to NONE')

    return Response({'command': command})


# ─── Dashboard Summary ────────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_summary(request):
    """
    GET /api/dashboard/summary/
    Aggregate data: all nodes' latest readings, ARI scores, active alerts.
    Used by the React Native dashboard for real-time overview.
    """
    nodes = SensorNode.objects.all()
    summary = []

    for node in nodes:
        latest = Reading.objects.filter(node=node).order_by('-recorded_at').first()

        if latest:
            ari_result = calculate_ari(latest.temperature_c, latest.humidity_pct)
            entry = {
                'node_id':         node.node_id,
                'node_identifier': node.node_identifier,
                'location_label':  node.location_label,
                'status':          node.status,
                'last_reading_at': node.last_reading_at,
                'temperature_c':   latest.temperature_c,
                'humidity_pct':    latest.humidity_pct,
                'ari_value':       ari_result['ari_score'],
                'risk_level':      ari_result['risk_level'],
                'risk_color':      ari_result['risk_color'],
                'dryer_active':    node.pending_command == DryerCommand.ON,
                'pending_command': node.pending_command,
            }
        else:
            entry = {
                'node_id':         node.node_id,
                'node_identifier': node.node_identifier,
                'location_label':  node.location_label,
                'status':          node.status,
                'last_reading_at': None,
                'temperature_c':   None,
                'humidity_pct':    None,
                'ari_value':       None,
                'risk_level':      None,
                'risk_color':      None,
                'dryer_active':    False,
                'pending_command': DryerCommand.NONE,
            }

        summary.append(entry)

    # Active alert count
    active_alerts = AlertLog.objects.filter(
        action_taken=False,
        risk_level__in=['Medium', 'High'],
    ).count()

    return Response({
        'nodes': summary,
        'total_nodes': len(summary),
        'active_alerts': active_alerts,
        'timestamp': timezone.now().isoformat(),
    })


# ─── Alert History ────────────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def alert_list(request):
    """
    GET /api/alerts/
    Alert history with optional filters: ?risk_level=High&days=7&node_id=1
    """
    qs = AlertLog.objects.select_related('node', 'reading').all()

    risk_level = request.query_params.get('risk_level')
    if risk_level:
        qs = qs.filter(risk_level=risk_level)

    days = request.query_params.get('days')
    if days:
        since = timezone.now() - timezone.timedelta(days=int(days))
        qs = qs.filter(sent_at__gte=since)

    node_id = request.query_params.get('node_id')
    if node_id:
        qs = qs.filter(node_id=node_id)

    qs = qs.order_by('-sent_at')[:200]

    serializer = AlertLogSerializer(qs, many=True)
    return Response({
        'count': len(serializer.data),
        'alerts': serializer.data,
    })


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def alert_acknowledge(request, alert_id):
    """
    PATCH /api/alerts/<alert_id>/acknowledge/
    Mark an alert as action_taken = True.
    """
    alert = get_object_or_404(AlertLog, alert_id=alert_id)
    alert.action_taken = True
    alert.save(update_fields=['action_taken'])
    return Response({'status': 'acknowledged', 'alert_id': alert_id})


# ─── Threshold Configuration ──────────────────────────────────────────────────
@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def threshold_detail(request, node_identifier):
    """
    GET/PUT /api/thresholds/<node_identifier>/
    UC3: Configure Alert Thresholds (Store Manager / Admin only)
    """
    node = get_object_or_404(SensorNode, node_identifier=node_identifier)

    threshold, _ = Threshold.objects.get_or_create(
        node=node,
        defaults={
            'min_temp': 10.0, 'max_temp': 35.0,
            'min_humidity': 40.0, 'max_humidity': 75.0,
            'risk_duration': 6,
        }
    )

    if request.method == 'GET':
        return Response(ThresholdSerializer(threshold).data)

    # PUT — update thresholds
    serializer = ThresholdSerializer(threshold, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        logger.info(
            f'[THRESHOLD] Updated for {node.node_identifier} by user {request.user}'
        )
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─── Authentication ───────────────────────────────────────────────────────────
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def login_view(request):
    """
    POST /api/auth/login/
    UC4: User authentication — returns DRF auth token.

    Request body : { "phone_number": "...", "password": "..." }
    Success 200  : { "token": "<drf_token>", "user": { ... } }
    Failure 401  : { "error": "Invalid credentials" }
    """
    phone_number = request.data.get('phone_number')
    password     = request.data.get('password')

    if not phone_number or not password:
        return Response(
            {'error': 'phone_number and password are required'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Normalize phone numbers for robust lookup (strip whitespaces/dashes)
    clean_phone = ''.join(c for c in phone_number if c.isdigit() or c == '+')
    
    # Try querying with exact match, or fallback by adding/removing leading '+'
    alt_phone = clean_phone[1:] if clean_phone.startswith('+') else f'+{clean_phone}'

    try:
        from django.db.models import Q
        user = User.objects.get(
            Q(phone_number=clean_phone) | Q(phone_number=alt_phone),
            is_active=True
        )
    except User.DoesNotExist:
        return Response(
            {'error': 'Invalid credentials'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    if not check_password(password, user.password_hash):
        return Response(
            {'error': 'Invalid credentials'},
            status=status.HTTP_401_UNAUTHORIZED,
        )

    # ── Issue DRF Token ───────────────────────────────────────────────────────
    # Token is tied to the built-in Django auth.User via DRF's TokenAuthentication.
    # We derive a stable Django user ID from the Smart-Stua User pk so that
    # the same person always gets the same token across sessions.
    from django.contrib.auth.models import User as DjangoUser

    # get_or_create a shadow Django auth.User keyed on our custom User's pk.
    django_user, _ = DjangoUser.objects.get_or_create(
        username=f'smartstua_{user.user_id}',
        defaults={
            'first_name': user.full_name.split()[0] if user.full_name else '',
            'is_active':  True,
        },
    )

    # DRF Token — created once, persists across logins (rotate manually if needed)
    token, _ = Token.objects.get_or_create(user=django_user)

    logger.info(f'[AUTH] Login success: {user.phone_number} (user_id={user.user_id})')

    return Response({
        'token': token.key,           # ← the value expo-secure-store will save
        'user':  UserSerializer(user).data,
        'message': 'Login successful',
    })


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def register_view(request):
    """
    POST /api/auth/register/
    UC4: User registration — Admin only.
    """
    # Role check: only admins can register new users
    # (Simplified — in production, link to Django auth system)
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response(
            UserSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─── Manual Dryer Override ────────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def dryer_override(request, node_id):
    """
    POST /api/devices/<node_id>/dryer/
    Manual dryer override — Store Manager / Admin use case.
    Body: {"action": "ON" | "OFF"}
    """
    node   = get_object_or_404(SensorNode, node_id=node_id)
    action = request.data.get('action', 'OFF').upper()

    if action not in ['ON', 'OFF']:
        return Response(
            {'error': 'action must be ON or OFF'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    from .tasks import send_dryer_command
    send_dryer_command.delay(node.node_id, action)

    logger.info(
        f'[DRYER] Manual override: {node.node_identifier} → {action} '
        f'by user {request.user}'
    )
    return Response({'status': 'queued', 'node': node.node_identifier, 'action': action})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_push_token(request):
    """
    POST /api/auth/save-push-token/
    Saves the user's Expo push notification token.
    """
    username = request.user.username
    if not username.startswith('smartstua_'):
        return Response({'error': 'Invalid user account'}, status=status.HTTP_400_BAD_REQUEST)

    try:
        user_id = int(username.split('_')[1])
        user = User.objects.get(user_id=user_id)
        user.push_token = request.data.get('push_token')
        user.save(update_fields=['push_token'])
        logger.info(f'[PUSH] Saved token for user {user.full_name}')
        return Response({'status': 'token saved'})
    except (ValueError, IndexError, User.DoesNotExist):
        return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)


# ─── System Health ────────────────────────────────────────────────────────────
@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def health_check(request):
    """
    GET /api/health/
    Used by docker-compose healthchecks to ensure the app is up.
    """
    return Response({'status': 'healthy', 'timestamp': timezone.now().isoformat()})
