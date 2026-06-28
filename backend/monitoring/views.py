"""
Smart-Stua API Views — RBAC-enforced
======================================
All node-scoped endpoints now enforce ownership:
  - Farmers / Store Managers see only their own registered nodes.
  - Admin role has global visibility across all nodes and data.

RBAC enforcement is provided by monitoring.permissions:
  - get_smartstua_user(request.user)  → resolve to monitoring.User
  - assert_node_access(user_obj, node) → raise 403 if not owner/admin
  - is_admin(user_obj)                → True for admin role
"""

import logging
from django.utils import timezone
from django.contrib.auth.hashers import check_password
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.authtoken.models import Token

from .models import SensorNode, Reading, AlertLog, Threshold, User, DryerCommand, UserRole
from .serializers import (
    SensorNodeSerializer, ReadingSerializer, AlertLogSerializer,
    ThresholdSerializer, SensorPayloadSerializer, DashboardNodeSummarySerializer,
    DryerCommandSerializer, UserSerializer, UserRegistrationSerializer,
    NodeRegistrationSerializer,
)
from .ari_algorithm import calculate_ari, get_risk_summary
from .permissions import get_smartstua_user, assert_node_access, is_admin
import hmac

logger = logging.getLogger(__name__)


# ─── DFD 1.0: Capture Sensor Data ────────────────────────────────────────────
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def receive_reading(request):
    """
    POST /api/readings/
    Accepts JSON from ESP32 sensor nodes.
    Auth: per-node API key in payload (not Bearer token).
    Rate-limited: 60 requests/min per node_id (django-ratelimit).
    """
    from django_ratelimit.core import is_ratelimited

    limited = is_ratelimited(
        request,
        group='iot_ingestion',
        key='post:node_id',
        rate='60/m',
        method='POST',
        increment=True,
    )
    if limited:
        logger.warning(f'[API] Rate limit exceeded for node: {request.data.get("node_id")}')
        return Response(
            {'error': 'Rate limit exceeded. Maximum 60 readings/minute per node.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    serializer = SensorPayloadSerializer(data=request.data)
    if not serializer.is_valid():
        logger.warning(f'[API] Invalid sensor payload: {serializer.errors}')
        return Response(
            {'error': 'Invalid payload', 'details': serializer.errors},
            status=status.HTTP_400_BAD_REQUEST,
        )

    data = serializer.validated_data
    node = data['_node']

    reading = Reading.objects.create(
        node=node,
        temperature_c=data['temperature'],
        humidity_pct=data['humidity'],
        moisture_pct=data.get('moisture_pct'),
        device_ts=data.get('device_ts'),
    )

    node.last_reading_at = timezone.now()
    node.save(update_fields=['last_reading_at'])

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
    - Admin: returns ALL sensor nodes across the platform.
    - Farmer/Store Manager: returns ONLY nodes they own.
    """
    user_obj = get_smartstua_user(request.user)

    if is_admin(user_obj):
        nodes = SensorNode.objects.prefetch_related('readings', 'readings__alert').all()
    else:
        if user_obj is None:
            return Response({'error': 'User account not found.'}, status=status.HTTP_403_FORBIDDEN)
        nodes = SensorNode.objects.prefetch_related(
            'readings', 'readings__alert'
        ).filter(owner=user_obj)

    serializer = SensorNodeSerializer(nodes, many=True)
    return Response(serializer.data)


# ─── Device Registration (Plug-and-Play) ──────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def device_register(request):
    """
    POST /api/devices/register/
    Register a new sensor node. The requesting user becomes the node owner.
    Admins can register nodes without becoming the owner (nodes assigned to them).
    """
    user_obj = get_smartstua_user(request.user)
    if user_obj is None:
        return Response({'error': 'User account not found.'}, status=status.HTTP_403_FORBIDDEN)

    serializer = NodeRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        node = serializer.save(owner=user_obj)
        logger.info(
            f'[DEVICE] Registered: {node.node_identifier} '
            f'(MAC: {node.mac_address}) by {user_obj.full_name} (owner)'
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─── Historical Readings ──────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def device_readings(request, node_id):
    """
    GET /api/devices/<node_id>/readings/
    Historical readings. Enforces node ownership.
    """
    node = get_object_or_404(SensorNode, node_id=node_id)
    user_obj = get_smartstua_user(request.user)
    assert_node_access(user_obj, node)

    days  = int(request.query_params.get('days', 7))
    limit = int(request.query_params.get('limit', 200))
    since = timezone.now() - timezone.timedelta(days=days)

    readings = Reading.objects.filter(
        node=node, recorded_at__gte=since,
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
    Latest reading + ARI. Enforces node ownership.
    """
    node = get_object_or_404(SensorNode, node_id=node_id)
    user_obj = get_smartstua_user(request.user)
    assert_node_access(user_obj, node)

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
    ESP32 polling endpoint. Auth: per-node api_key query param (timing-safe).
    No user session needed — device-to-device auth.
    """
    api_key = request.query_params.get('api_key', '')
    node = get_object_or_404(SensorNode, node_identifier=node_id)

    if not hmac.compare_digest(node.api_key, api_key):
        return Response({'error': 'Unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)

    command = node.pending_command
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
    - Admin: aggregate data for ALL nodes platform-wide.
    - Farmer/Store Manager: only their own nodes.
    """
    user_obj = get_smartstua_user(request.user)

    if is_admin(user_obj):
        nodes = SensorNode.objects.all()
        # Admin sees all unacknowledged alerts
        active_alerts = AlertLog.objects.filter(
            action_taken=False, risk_level__in=['Medium', 'High'],
        ).count()
    else:
        if user_obj is None:
            return Response({'error': 'User account not found.'}, status=status.HTTP_403_FORBIDDEN)
        nodes = SensorNode.objects.filter(owner=user_obj)
        # Farmer/Manager sees only alerts for their own nodes
        active_alerts = AlertLog.objects.filter(
            node__owner=user_obj,
            action_taken=False,
            risk_level__in=['Medium', 'High'],
        ).count()

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
                'moisture_pct':    latest.moisture_pct,
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
                'moisture_pct':    None,
                'ari_value':       None,
                'risk_level':      None,
                'risk_color':      None,
                'dryer_active':    False,
                'pending_command': DryerCommand.NONE,
            }
        summary.append(entry)

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
    - Admin: all alerts across the platform.
    - Farmer/Manager: only alerts for their own nodes.
    """
    user_obj = get_smartstua_user(request.user)
    qs = AlertLog.objects.select_related('node', 'reading').all()

    if not is_admin(user_obj):
        if user_obj is None:
            return Response({'error': 'User account not found.'}, status=status.HTTP_403_FORBIDDEN)
        qs = qs.filter(node__owner=user_obj)

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
    return Response({'count': len(serializer.data), 'alerts': serializer.data})


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def alert_acknowledge(request, alert_id):
    """PATCH /api/alerts/<alert_id>/acknowledge/"""
    alert = get_object_or_404(AlertLog, alert_id=alert_id)
    user_obj = get_smartstua_user(request.user)
    # Only node owner or admin can acknowledge
    if not is_admin(user_obj) and alert.node and alert.node.owner_id != user_obj.user_id:
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied('You cannot acknowledge alerts for nodes you do not own.')
    alert.action_taken = True
    alert.save(update_fields=['action_taken'])
    return Response({'status': 'acknowledged', 'alert_id': alert_id})


# ─── Threshold Configuration ──────────────────────────────────────────────────
@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def threshold_detail(request, node_identifier):
    """
    GET/PUT /api/thresholds/<node_identifier>/
    Only the node owner or admin can view/update thresholds.
    """
    node = get_object_or_404(SensorNode, node_identifier=node_identifier)
    user_obj = get_smartstua_user(request.user)
    assert_node_access(user_obj, node)

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

    serializer = ThresholdSerializer(threshold, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        logger.info(f'[THRESHOLD] Updated for {node.node_identifier} by {user_obj.full_name}')
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─── Authentication ───────────────────────────────────────────────────────────
@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def login_view(request):
    """
    POST /api/auth/login/
    Rate-limited: 10 requests/min per IP (django-ratelimit applied in middleware).
    """
    from django_ratelimit.core import is_ratelimited
    limited = is_ratelimited(
        request, group='login', key='ip', rate='10/m', method='POST', increment=True
    )
    if limited:
        return Response(
            {'error': 'Too many login attempts. Please wait before trying again.'},
            status=status.HTTP_429_TOO_MANY_REQUESTS,
        )

    phone_number = request.data.get('phone_number')
    password     = request.data.get('password')

    if not phone_number or not password:
        return Response(
            {'error': 'phone_number and password are required'},
            status=status.HTTP_400_BAD_REQUEST,
        )

    clean_phone = ''.join(c for c in phone_number if c.isdigit() or c == '+')
    alt_phone = clean_phone[1:] if clean_phone.startswith('+') else f'+{clean_phone}'

    try:
        from django.db.models import Q
        user = User.objects.get(
            Q(phone_number=clean_phone) | Q(phone_number=alt_phone),
            is_active=True
        )
    except User.DoesNotExist:
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

    if not check_password(password, user.password_hash):
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)

    from django.contrib.auth.models import User as DjangoUser
    django_user, _ = DjangoUser.objects.get_or_create(
        username=f'smartstua_{user.user_id}',
        defaults={'first_name': user.full_name.split()[0] if user.full_name else '', 'is_active': True},
    )
    token, _ = Token.objects.get_or_create(user=django_user)

    logger.info(f'[AUTH] Login success: {user.phone_number} (user_id={user.user_id})')
    return Response({
        'token': token.key,
        'user':  UserSerializer(user).data,
        'message': 'Login successful',
    })


@api_view(['POST'])
@authentication_classes([])
@permission_classes([AllowAny])
def register_view(request):
    """POST /api/auth/register/"""
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response(UserSerializer(user).data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─── Manual Dryer Override ────────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def dryer_override(request, node_id):
    """
    POST /api/devices/<node_id>/dryer/
    Only node owner or admin can issue dryer commands.
    """
    node = get_object_or_404(SensorNode, node_id=node_id)
    user_obj = get_smartstua_user(request.user)
    assert_node_access(user_obj, node)

    action = request.data.get('action', 'OFF').upper()
    if action not in ['ON', 'OFF']:
        return Response({'error': 'action must be ON or OFF'}, status=status.HTTP_400_BAD_REQUEST)

    from .tasks import send_dryer_command
    send_dryer_command.delay(node.node_id, action)
    logger.info(f'[DRYER] Manual override: {node.node_identifier} → {action} by {user_obj.full_name}')
    return Response({'status': 'queued', 'node': node.node_identifier, 'action': action})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def save_push_token(request):
    """POST /api/auth/save-push-token/"""
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


# ─── Node Detail ─────────────────────────────────────────────────────────────
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def device_detail(request, node_id):
    """GET /api/devices/<node_id>/ — enforces ownership."""
    node = get_object_or_404(SensorNode, node_id=node_id)
    user_obj = get_smartstua_user(request.user)
    assert_node_access(user_obj, node)
    return Response(SensorNodeSerializer(node).data)


# ─── Node Update ─────────────────────────────────────────────────────────────
@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def device_update(request, node_id):
    """PATCH /api/devices/<node_id>/update/ — enforces ownership."""
    node = get_object_or_404(SensorNode, node_id=node_id)
    user_obj = get_smartstua_user(request.user)
    assert_node_access(user_obj, node)

    serializer = SensorNodeSerializer(node, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        logger.info(f'[DEVICE] Updated: {node.node_identifier} by {user_obj.full_name}')
        return Response(serializer.data)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─── Node Soft-Delete ─────────────────────────────────────────────────────────
@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def device_delete(request, node_id):
    """DELETE /api/devices/<node_id>/delete/ — enforces ownership."""
    node = get_object_or_404(SensorNode, node_id=node_id)
    user_obj = get_smartstua_user(request.user)
    assert_node_access(user_obj, node)

    node.status = 'inactive'
    node.save(update_fields=['status'])
    logger.info(f'[DEVICE] Soft-deleted: {node.node_identifier} by {user_obj.full_name}')
    return Response({'status': 'deactivated', 'node_identifier': node.node_identifier})


# ─── Rotate API Key ───────────────────────────────────────────────────────────
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def rotate_api_key(request, node_id):
    """POST /api/devices/<node_id>/rotate-key/ — enforces ownership."""
    node = get_object_or_404(SensorNode, node_id=node_id)
    user_obj = get_smartstua_user(request.user)
    assert_node_access(user_obj, node)

    new_key = node.rotate_api_key()
    logger.warning(f'[SECURITY] API key rotated for {node.node_identifier} by {user_obj.full_name}')
    return Response({
        'node_identifier': node.node_identifier,
        'api_key': new_key,
        'message': 'API key rotated. Update your device firmware configuration immediately.',
    })


# ─── System Health ────────────────────────────────────────────────────────────
@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def health_check(request):
    """GET /api/health/ — used by Docker and Render healthchecks."""
    return Response({'status': 'healthy', 'timestamp': timezone.now().isoformat()})


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def last_error_view(request):
    """GET /api/last-error/ — temporary endpoint to view the last 500 error traceback."""
    import os
    from django.http import HttpResponse
    log_path = '/tmp/last_error.txt'
    if os.name == 'nt':
        log_path = 'last_error.txt'
    if not os.path.exists(log_path):
        return HttpResponse("No error recorded yet.", content_type="text/plain")
    with open(log_path, 'r') as f:
        content = f.read()
    return HttpResponse(content, content_type="text/plain")


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def run_migrations_view(request):
    """GET /api/run-migrations/ — runs django migrations and returns stdout."""
    from django.core.management import call_command
    from django.http import HttpResponse
    from io import StringIO
    out = StringIO()
    try:
        call_command('migrate', interactive=False, stdout=out)
        return HttpResponse(out.getvalue(), content_type="text/plain")
    except Exception as e:
        import traceback
        return HttpResponse(f"Error during migration:\n{traceback.format_exc()}", content_type="text/plain", status=500)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def create_superuser_view(request):
    """GET /api/create-superuser/ — seeds a superuser account."""
    from django.contrib.auth.models import User as DjangoUser
    from django.http import HttpResponse
    import os
    
    username = 'admin'
    email = os.environ.get('ADMIN_EMAIL', 'raphaelocitti@gmail.com')
    password = os.environ.get('ADMIN_DEFAULT_PASSWORD', 'SmartStua@Change-Me!')
    
    try:
        if not DjangoUser.objects.filter(username=username).exists():
            DjangoUser.objects.create_superuser(
                username=username,
                email=email,
                password=password,
            )
            return HttpResponse(f"Superuser '{username}' created successfully.", content_type="text/plain")
        else:
            # Let's update password just in case they forgot it or want to reset it
            user = DjangoUser.objects.get(username=username)
            user.set_password(password)
            user.save()
            return HttpResponse(f"Superuser '{username}' already exists. Password reset/updated successfully.", content_type="text/plain")
    except Exception as e:
        import traceback
        return HttpResponse(f"Error creating superuser:\n{traceback.format_exc()}", content_type="text/plain", status=500)


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def view_bridge_logs_view(request):
    """GET /api/bridge-logs/ — view the logs of the background mqtt bridge."""
    import os
    from django.http import HttpResponse
    log_path = '/app/logs/mqtt_bridge.log'
    if not os.path.exists(log_path):
        log_dir = '/app/logs'
        if os.path.exists(log_dir):
            files = os.listdir(log_dir)
            return HttpResponse(f"Log file not found. Files in {log_dir}: {files}", content_type="text/plain")
        else:
            return HttpResponse(f"Log file and /app/logs directory do not exist.", content_type="text/plain")
            
    with open(log_path, 'r') as f:
        content = f.read()
    return HttpResponse(content, content_type="text/plain")


@api_view(['GET'])
@authentication_classes([])
@permission_classes([AllowAny])
def debug_processes_view(request):
    """GET /api/debug-processes/ — lists running processes inside the container."""
    import subprocess
    from django.http import HttpResponse
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True, check=True)
        return HttpResponse(result.stdout, content_type="text/plain")
    except Exception as e:
        try:
            result = subprocess.run(['ps'], capture_output=True, text=True, check=True)
            return HttpResponse(result.stdout, content_type="text/plain")
        except Exception as e2:
            import traceback
            return HttpResponse(f"Error running ps:\n{traceback.format_exc()}", content_type="text/plain", status=500)
