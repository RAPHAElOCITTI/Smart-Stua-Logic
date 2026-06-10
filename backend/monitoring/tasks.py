"""
Celery Tasks for Smart-Stua Monitoring
=======================================
Maps to DFD Process 3.0 (Generate Alerts) and the
Scheduler & Alert Dispatcher in the high-level architecture diagram.

Tasks:
  - process_sensor_data(reading_id)    : Compute ARI → store alert → dispatch
  - send_sms_alert(alert_id)           : Send Twilio SMS to registered users
  - send_dryer_command(node_id, action): Set pending dryer command for ESP32
  - calculate_all_cumulative_durations : Periodic (every 15 min) duration tracking
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

    1. Load reading from DB
    2. Calculate continuous exposure duration (for duration factor)
    3. Compute ARI score
    4. Store alert in AlertLogs if ARI ≥ Medium threshold
    5. Dispatch alert and dryer command if High risk
    """
    from .models import Reading, AlertLog, SensorNode, AlertType
    from .ari_algorithm import calculate_ari, RISK_HIGH_THRESHOLD, RISK_MEDIUM_THRESHOLD

    try:
        reading = Reading.objects.select_related('node', 'node__threshold').get(
            reading_id=reading_id
        )
    except Reading.DoesNotExist:
        logger.error(f'[ARI] Reading {reading_id} not found')
        return

    node = reading.node

    # Calculate continuous high-risk duration
    duration_hours = _get_continuous_risk_duration(node)

    # Compute ARI
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

    # Only create AlertLog for Medium or High risk
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
            # Dispatch SMS asynchronously
            send_sms_alert.delay(alert.alert_id)
            # Dispatch Push Notification asynchronously
            send_push_alert.delay(alert.alert_id)

        # Trigger dryer for High risk
        if ari_score >= RISK_HIGH_THRESHOLD:
            send_dryer_command.delay(node.node_id, 'ON')
            logger.warning(
                f'[DRYER] HIGH RISK at {node.node_identifier} — dryer command queued'
            )
        else:
            # Medium risk: ensure dryer is off unless already manually activated
            if node.pending_command == 'ON':
                logger.info(f'[DRYER] Medium risk at {node.node_identifier} — dryer stays ON')

    else:
        # Low risk: clear dryer command if it was auto-set
        if node.pending_command == 'ON':
            send_dryer_command.delay(node.node_id, 'OFF')
            logger.info(
                f'[DRYER] Risk cleared at {node.node_identifier} — dryer OFF command queued'
            )

    # Check physical threshold breaches
    if hasattr(node, 'threshold') and node.threshold:
        thresh = node.threshold
        temp_breach = None
        hum_breach = None

        if reading.temperature_c > thresh.max_temp:
            temp_breach = f"Temperature ({reading.temperature_c:.1f}°C) exceeds maximum threshold of {thresh.max_temp:.1f}°C."
        elif reading.temperature_c < thresh.min_temp:
            temp_breach = f"Temperature ({reading.temperature_c:.1f}°C) falls below minimum threshold of {thresh.min_temp:.1f}°C."

        if reading.humidity_pct > thresh.max_humidity:
            hum_breach = f"Humidity ({reading.humidity_pct:.1f}%) exceeds maximum threshold of {thresh.max_humidity:.1f}%."
        elif reading.humidity_pct < thresh.min_humidity:
            hum_breach = f"Humidity ({reading.humidity_pct:.1f}%) falls below minimum threshold of {thresh.min_humidity:.1f}%."

        breaches = [b for b in [temp_breach, hum_breach] if b]
        if breaches:
            breach_msg = f"⚠️ THRESHOLD BREACH at Node: {node.node_identifier}\nLocation: {node.location_label}\n" + "\n".join(breaches)
            recipients = _get_alert_recipients(node)
            for recipient_phone in recipients:
                alert = AlertLog.objects.create(
                    node=node,
                    reading=reading,
                    ari_value=ari_score,
                    alert_type=AlertType.THRESHOLD_BREACH,
                    risk_level='High' if (reading.temperature_c > thresh.max_temp or reading.humidity_pct > thresh.max_humidity) else 'Medium',
                    message=breach_msg,
                    sent_to=recipient_phone,
                    action_taken=False,
                )
                send_sms_alert.delay(alert.alert_id)
                send_push_alert.delay(alert.alert_id)

    return {
        'reading_id': reading_id,
        'ari_score': ari_score,
        'risk_level': risk_level,
    }


# ─── SMS Alert Task ───────────────────────────────────────────────────────────
@shared_task(bind=True, max_retries=3, default_retry_delay=120)
def send_sms_alert(self, alert_id: int):
    """
    DFD Process 3.0: Generate Alerts → SMS/Email Gateway
    Sends Twilio SMS to farmer/store manager phone numbers.
    """
    from .models import AlertLog

    try:
        alert = AlertLog.objects.select_related('node').get(alert_id=alert_id)
    except AlertLog.DoesNotExist:
        logger.error(f'[SMS] Alert {alert_id} not found')
        return

    # Skip if credentials not configured
    if not all([settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN,
                settings.TWILIO_PHONE]):
        logger.warning('[SMS] Twilio credentials not configured — skipping SMS dispatch')
        return

    try:
        from twilio.rest import Client
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

        message = client.messages.create(
            body=alert.message,
            from_=settings.TWILIO_PHONE,
            to=alert.sent_to,
        )

        alert.sms_sid = message.sid
        alert.save(update_fields=['sms_sid'])

        logger.info(
            f'[SMS] Sent to {alert.sent_to} — SID={message.sid} '
            f'Risk={alert.risk_level} ARI={alert.ari_value}'
        )

    except Exception as exc:
        logger.error(f'[SMS] Failed for alert {alert_id}: {exc}')
        try:
            from twilio.base.exceptions import TwilioRestException
            if isinstance(exc, TwilioRestException):
                # Don't retry for client errors, authentication failures, or rate limit issues
                if exc.status in [400, 401, 403, 404, 429]:
                    logger.warning(
                        f'[SMS] Twilio permanent error (status {exc.status}, code {exc.code}) '
                        f'— skipping retry. Details: {exc.msg}'
                    )
                    alert.sms_sid = f"FAILED: {exc.code or exc.status}"
                    alert.save(update_fields=['sms_sid'])
                    return
        except ImportError:
            pass
        raise self.retry(exc=exc)


# ─── Push Notification Alert Task ─────────────────────────────────────────────
@shared_task
def send_push_alert(alert_id: int):
    """
    Sends an Expo Push Notification for a logged AlertLog entry
    to the corresponding user with a valid push_token.
    """
    from .models import AlertLog, User

    try:
        alert = AlertLog.objects.select_related('node').get(alert_id=alert_id)
    except AlertLog.DoesNotExist:
        logger.error(f'[PUSH] Alert {alert_id} not found')
        return

    # Find the user matching the recipient's phone number
    try:
        user = User.objects.get(phone_number=alert.sent_to, is_active=True)
    except User.DoesNotExist:
        logger.warning(f'[PUSH] User with phone {alert.sent_to} not found')
        return

    if not user.push_token:
        logger.info(f'[PUSH] No push token for user {user.full_name} — skipping push dispatch')
        return

    try:
        from exponent_server_sdk import PushClient, PushMessage
        
        # Determine title based on alert type or risk level
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
        logger.info(f'[PUSH] Sent to {user.full_name} ({user.phone_number}) successfully')
    except Exception as exc:
        logger.error(f'[PUSH] Failed to send push for alert {alert_id}: {exc}')


# ─── Dryer Command Task ───────────────────────────────────────────────────────
@shared_task(bind=True)
def send_dryer_command(self, node_id: int, action: str):
    """
    Set pending dryer command on SensorNode for ESP32 polling.
    The ESP32 polls /api/devices/<node_id>/command/ after each reading.
    """
    from .models import SensorNode, DryerCommand

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
    """
    Periodic Celery Beat task (every 15 minutes).
    Calculates continuous hours of high-risk exposure for each active node.
    Used to populate the duration factor in future ARI calculations.
    Stored as a node annotation — no separate model needed.
    """
    from .models import SensorNode
    from .ari_algorithm import RISK_HIGH_THRESHOLD, calculate_ari

    active_nodes = SensorNode.objects.filter(status='active')
    for node in active_nodes:
        duration = _get_continuous_risk_duration(node)
        logger.debug(
            f'[DURATION] {node.node_identifier}: '
            f'{duration:.1f}h continuous high-risk exposure'
        )


# ─── Helpers ─────────────────────────────────────────────────────────────────
def _get_continuous_risk_duration(node) -> float:
    """
    Calculate hours of continuous high-risk conditions for a node.
    Looks back through recent readings until it finds a Low-risk or a gap > 30 min.
    """
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
            # Check for gap (> 30 min) — breaks continuity
            if prev_ts and (prev_ts - reading.recorded_at).total_seconds() > 1800:
                break
            continuous_start = reading.recorded_at
            prev_ts = reading.recorded_at
        else:
            # Non-risky reading breaks the streak
            break

    if continuous_start is None:
        return 0.0

    duration = (timezone.now() - continuous_start).total_seconds() / 3600
    return max(0.0, duration)


def _build_alert_message(node, reading, ari_result: dict) -> str:
    """Build human-readable SMS alert message."""
    risk = ari_result['risk_level'].upper()
    ari  = ari_result['ari_score']
    action = ari_result['recommended_action']

    lines = [
        f'⚠️ SMART-STUA ALERT [{risk} RISK]',
        f'Location: {node.location_label}',
        f'Node: {node.node_identifier}',
        f'Temperature: {reading.temperature_c:.1f}°C',
        f'Humidity: {reading.humidity_pct:.1f}%',
        f'ARI Score: {ari:.1f}/100',
        f'Action: {action}',
        f'Time: {reading.recorded_at.strftime("%Y-%m-%d %H:%M UTC")}',
    ]
    return '\n'.join(lines)


def _get_alert_recipients(node) -> list[str]:
    """Get phone numbers of all Farmers and Store Managers to receive alerts."""
    from .models import User, UserRole

    phones = list(
        User.objects.filter(
            role__in=[UserRole.FARMER, UserRole.STORE_MANAGER],
            is_active=True,
        ).values_list('phone_number', flat=True)
    )

    if not phones:
        # Fallback: log warning but don't fail silently
        logger.warning(
            f'[ALERT] No active farmers/managers found to notify for node '
            f'{node.node_identifier}'
        )

    return phones


@shared_task
def check_offline_nodes():
    """
    Periodic task (e.g. runs every 15 minutes) to check for offline sensor nodes.
    If a node hasn't sent a reading in the last 30 minutes, generate an alert.
    """
    from .models import SensorNode, AlertLog, AlertType, NodeStatus
    
    thirty_minutes_ago = timezone.now() - timedelta(minutes=30)
    # Get active nodes that have not reported recently
    offline_nodes = SensorNode.objects.filter(
        status=NodeStatus.ACTIVE,
        last_reading_at__lt=thirty_minutes_ago
    ) | SensorNode.objects.filter(
        status=NodeStatus.ACTIVE,
        last_reading_at__isnull=True,
        installed_at__lt=thirty_minutes_ago
    )

    for node in offline_nodes:
        # Check if we already logged an offline alert since its last reading
        already_alerted = AlertLog.objects.filter(
            node=node,
            alert_type=AlertType.NODE_OFFLINE,
            sent_at__gt=node.last_reading_at if node.last_reading_at else node.installed_at
        ).exists()
        if already_alerted:
            continue

        last_seen = node.last_reading_at.strftime("%Y-%m-%d %H:%M UTC") if node.last_reading_at else "Never"
        message = (
            f"❌ NODE OFFLINE ALERT\n"
            f"Node: {node.node_identifier}\n"
            f"Location: {node.location_label}\n"
            f"Status: Device offline (no reports for > 30 minutes)\n"
            f"Last Active: {last_seen}"
        )
        
        recipients = _get_alert_recipients(node)
        for phone in recipients:
            alert = AlertLog.objects.create(
                node=node,
                alert_type=AlertType.NODE_OFFLINE,
                risk_level='High',
                message=message,
                sent_to=phone,
                action_taken=False,
            )
            send_sms_alert.delay(alert.alert_id)
            send_push_alert.delay(alert.alert_id)
        
        logger.warning(f"[OFFLINE] Node {node.node_identifier} detected offline and alert logged.")
