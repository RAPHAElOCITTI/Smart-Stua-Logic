"""
Celery Tasks for Smart-Stua Monitoring
=======================================
Alert recipient scoping (updated for RBAC):
  - ARI / threshold alerts → node.owner + all admin users.
  - Node-offline alerts    → node.owner + all admin users.
  - SMS dispatched via sms_utils.send_sms (reusable utility).
"""

import logging
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from celery import shared_task

logger = logging.getLogger(__name__)


# ─── Main Processing Task ─────────────────────────────────────────────────────
@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def process_sensor_data(self, reading_id: int):
    """
    DFD Process 2.0: Process ARI
    Called after every successful reading POST from a sensor node.
    """
    from .models import Reading, AlertLog, SensorNode, AlertType
    from .ari_algorithm import calculate_ari, RISK_HIGH_THRESHOLD, RISK_MEDIUM_THRESHOLD

    try:
        reading = Reading.objects.select_related('node', 'node__threshold', 'node__owner').get(
            reading_id=reading_id
        )
    except Reading.DoesNotExist:
        logger.error(f'[ARI] Reading {reading_id} not found')
        return

    node = reading.node
    duration_hours = _get_continuous_risk_duration(node)

    ari_result = calculate_ari(
        temperature=reading.temperature_c,
        humidity=reading.humidity_pct,
        duration_hours=duration_hours,
    )

    ari_score  = ari_result['ari_score']
    risk_level = ari_result['risk_level']

    logger.info(
        f'[ARI] Node={node.node_identifier} '
        f'T={reading.temperature_c}°C H={reading.humidity_pct}% '
        f'Duration={duration_hours:.1f}h → ARI={ari_score:.1f} ({risk_level})'
    )

    if ari_score >= RISK_MEDIUM_THRESHOLD:
        message = _build_alert_message(node, reading, ari_result)
        recipients = _get_alert_recipients(node)

        for recipient_phone in recipients:
            alert = AlertLog.objects.create(
                node=node,
                reading=reading,
                ari_value=ari_score,
                risk_level=risk_level,
                message=message,
                sent_to=recipient_phone,
                action_taken=False,
            )
            send_sms_alert.delay(alert.alert_id)
            send_push_alert.delay(alert.alert_id)

        if ari_score >= RISK_HIGH_THRESHOLD:
            send_dryer_command.delay(node.node_id, 'ON')
            logger.warning(f'[DRYER] HIGH RISK at {node.node_identifier} — dryer command queued')
        else:
            if node.pending_command == 'ON':
                logger.info(f'[DRYER] Medium risk at {node.node_identifier} — dryer stays ON')

    else:
        if node.pending_command == 'ON':
            send_dryer_command.delay(node.node_id, 'OFF')
            logger.info(f'[DRYER] Risk cleared at {node.node_identifier} — dryer OFF command queued')

    # Threshold breach checks
    if hasattr(node, 'threshold') and node.threshold:
        thresh = node.threshold
        temp_breach = hum_breach = None

        if reading.temperature_c > thresh.max_temp:
            temp_breach = f"Temperature ({reading.temperature_c:.1f}°C) exceeds max {thresh.max_temp:.1f}°C."
        elif reading.temperature_c < thresh.min_temp:
            temp_breach = f"Temperature ({reading.temperature_c:.1f}°C) below min {thresh.min_temp:.1f}°C."

        if reading.humidity_pct > thresh.max_humidity:
            hum_breach = f"Humidity ({reading.humidity_pct:.1f}%) exceeds max {thresh.max_humidity:.1f}%."
        elif reading.humidity_pct < thresh.min_humidity:
            hum_breach = f"Humidity ({reading.humidity_pct:.1f}%) below min {thresh.min_humidity:.1f}%."

        breaches = [b for b in [temp_breach, hum_breach] if b]
        if breaches:
            breach_msg = (
                f"⚠️ THRESHOLD BREACH at Node: {node.node_identifier}\n"
                f"Location: {node.location_label}\n" + "\n".join(breaches)
            )
            recipients = _get_alert_recipients(node)
            for recipient_phone in recipients:
                alert = AlertLog.objects.create(
                    node=node,
                    reading=reading,
                    ari_value=ari_score,
                    alert_type=AlertType.THRESHOLD_BREACH,
                    risk_level='High' if (
                        reading.temperature_c > thresh.max_temp
                        or reading.humidity_pct > thresh.max_humidity
                    ) else 'Medium',
                    message=breach_msg,
                    sent_to=recipient_phone,
                    action_taken=False,
                )
                send_sms_alert.delay(alert.alert_id)
                send_push_alert.delay(alert.alert_id)

    return {'reading_id': reading_id, 'ari_score': ari_score, 'risk_level': risk_level}


# ─── SMS Alert Task ───────────────────────────────────────────────────────────
@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def send_sms_alert(self, alert_id: int):
    """
    Dispatch SMS via sms_utils. Retries up to 3 times on transient failures.
    Permanent Twilio errors (4xx) are not retried.
    """
    from .models import AlertLog
    from .sms_utils import send_sms

    try:
        alert = AlertLog.objects.select_related('node').get(alert_id=alert_id)
    except AlertLog.DoesNotExist:
        logger.error(f'[SMS] Alert {alert_id} not found')
        return

    sid = send_sms(to=alert.sent_to, body=alert.message)

    if sid:
        alert.sms_sid = sid
        alert.save(update_fields=['sms_sid'])
        logger.info(f'[SMS] Delivered alert {alert_id} → SID={sid}')
    else:
        # Permanent failure (no SID returned and no exception) — mark and skip retry
        logger.warning(f'[SMS] Alert {alert_id}: SMS returned no SID (credentials missing or permanent error)')


# ─── Push Notification Alert Task ─────────────────────────────────────────────
@shared_task
def send_push_alert(alert_id: int):
    """Expo push notification for an AlertLog entry."""
    from .models import AlertLog, User

    try:
        alert = AlertLog.objects.select_related('node').get(alert_id=alert_id)
    except AlertLog.DoesNotExist:
        logger.error(f'[PUSH] Alert {alert_id} not found')
        return

    try:
        user = User.objects.get(phone_number=alert.sent_to, is_active=True)
    except User.DoesNotExist:
        logger.warning(f'[PUSH] User with phone {alert.sent_to} not found')
        return

    if not user.push_token:
        logger.info(f'[PUSH] No push token for {user.full_name} — skipping')
        return

    try:
        from exponent_server_sdk import PushClient, PushMessage
        title = f"Smart-Stua Alert [{alert.risk_level} Risk]"
        if alert.alert_type == 'node_offline':
            title = "❌ Node Offline Warning"
        elif alert.alert_type == 'threshold_breach':
            title = "⚠️ Sensor Threshold Breach"

        response = PushClient().publish(
            PushMessage(
                to=user.push_token,
                title=title,
                body=alert.message,
                sound='default',
                channel_id='default',
                data={
                    'alert_id': alert.alert_id,
                    'node_identifier': alert.node.node_identifier if alert.node else None,
                },
            )
        )
        response.validate_response()
        logger.info(f'[PUSH] Sent to {user.full_name} successfully')
    except Exception as exc:
        logger.error(f'[PUSH] Failed for alert {alert_id}: {exc}')


# ─── Dryer Command Task ───────────────────────────────────────────────────────
@shared_task(bind=True)
def send_dryer_command(self, node_id: int, action: str):
    """Set pending dryer command on SensorNode for ESP32 polling."""
    from .models import SensorNode
    try:
        node = SensorNode.objects.get(node_id=node_id)
        node.pending_command = action
        node.save(update_fields=['pending_command'])
        logger.info(f'[CMD] Dryer command set: {node.node_identifier} → {action}')
    except SensorNode.DoesNotExist:
        logger.error(f'[CMD] SensorNode {node_id} not found')


# ─── Periodic Duration Tracking ───────────────────────────────────────────────
@shared_task
def calculate_all_cumulative_durations():
    """Periodic (every 15 min): track continuous high-risk exposure per node."""
    from .models import SensorNode
    active_nodes = SensorNode.objects.filter(status='active')
    for node in active_nodes:
        duration = _get_continuous_risk_duration(node)
        logger.debug(f'[DURATION] {node.node_identifier}: {duration:.1f}h continuous high-risk')


# ─── Offline Node Check ───────────────────────────────────────────────────────
@shared_task
def check_offline_nodes():
    """
    Periodic (every 2 min): flag nodes that haven't reported in 30+ minutes.
    Alerts go to node.owner + all admins.
    """
    from .models import SensorNode, AlertLog, AlertType, NodeStatus
    from .sms_utils import send_offline_sms

    thirty_minutes_ago = timezone.now() - timedelta(minutes=30)
    offline_nodes = SensorNode.objects.filter(
        status=NodeStatus.ACTIVE,
        last_reading_at__lt=thirty_minutes_ago
    ) | SensorNode.objects.filter(
        status=NodeStatus.ACTIVE,
        last_reading_at__isnull=True,
        installed_at__lt=thirty_minutes_ago
    )

    for node in offline_nodes:
        already_alerted = AlertLog.objects.filter(
            node=node,
            alert_type=AlertType.NODE_OFFLINE,
            sent_at__gt=node.last_reading_at if node.last_reading_at else node.installed_at
        ).exists()
        if already_alerted:
            continue

        last_seen = (
            node.last_reading_at.strftime("%Y-%m-%d %H:%M UTC")
            if node.last_reading_at else "Never"
        )
        recipients = _get_alert_recipients(node)
        for phone in recipients:
            alert = AlertLog.objects.create(
                node=node,
                alert_type=AlertType.NODE_OFFLINE,
                risk_level='High',
                message=(
                    f"❌ NODE OFFLINE\nNode: {node.node_identifier}\n"
                    f"Location: {node.location_label}\n"
                    f"Status: No reports >30 minutes\nLast Active: {last_seen}"
                ),
                sent_to=phone,
                action_taken=False,
            )
            send_sms_alert.delay(alert.alert_id)
            send_push_alert.delay(alert.alert_id)

        logger.warning(f'[OFFLINE] {node.node_identifier} offline — alerts dispatched')


# ─── Helpers ─────────────────────────────────────────────────────────────────
def _get_continuous_risk_duration(node) -> float:
    """Calculate hours of continuous high-risk conditions for a node."""
    from .models import Reading
    from .ari_algorithm import calculate_ari, RISK_MEDIUM_THRESHOLD

    readings = Reading.objects.filter(node=node).order_by('-recorded_at')[:96]
    if not readings:
        return 0.0

    continuous_start = None
    prev_ts = None

    for reading in readings:
        ari = calculate_ari(reading.temperature_c, reading.humidity_pct, 0.0)
        is_risky = ari['ari_score'] >= RISK_MEDIUM_THRESHOLD
        if is_risky:
            if prev_ts and (prev_ts - reading.recorded_at).total_seconds() > 1800:
                break
            continuous_start = reading.recorded_at
            prev_ts = reading.recorded_at
        else:
            break

    if continuous_start is None:
        return 0.0
    return max(0.0, (timezone.now() - continuous_start).total_seconds() / 3600)


def _build_alert_message(node, reading, ari_result: dict) -> str:
    """Build SMS alert message body."""
    from .sms_utils import build_ari_alert_body
    return build_ari_alert_body(node, reading, ari_result)


def _get_alert_recipients(node) -> list[str]:
    """
    Return phone numbers of people who should receive alerts for this node:
      1. The node's owner (Farmer or Store Manager).
      2. All active Admin users (system-wide oversight).

    This replaces the old broadcast-to-all-farmers approach.
    """
    from .models import User, UserRole

    phones = set()

    # 1. Node owner
    if node.owner and node.owner.is_active and node.owner.phone_number:
        phones.add(node.owner.phone_number)

    # 2. All active admins (platform-wide oversight)
    admin_phones = User.objects.filter(
        role=UserRole.ADMIN,
        is_active=True,
    ).values_list('phone_number', flat=True)
    phones.update(admin_phones)

    if not phones:
        logger.warning(
            f'[ALERT] No recipients found for node {node.node_identifier}. '
            'Ensure the node has an owner assigned and at least one admin exists.'
        )

    return list(phones)
