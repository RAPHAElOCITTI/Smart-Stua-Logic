"""
Smart-Stua — Twilio SMS Utility
================================
Reusable SMS dispatching module. Designed to be imported by Celery tasks
and any future view that needs to send an on-demand SMS.

Features:
  - Lazy Twilio client initialisation (no import cost if credentials absent)
  - Structured error handling with detailed logging
  - Returns Twilio message SID on success, None on failure
  - Graceful no-op when TWILIO_* env vars are not set (dev environments)

Usage:
    from monitoring.sms_utils import send_sms, send_alert_sms

    sid = send_sms(to='+256762038491', body='Hello from Smart-Stua!')
    sid = send_alert_sms(node, reading, ari_result)
"""

import logging
from django.conf import settings

logger = logging.getLogger(__name__)

# Cached Twilio client (initialised once per worker process)
_twilio_client = None


def _get_client():
    """
    Return a cached Twilio REST Client, or None if credentials are missing.
    Thread-safe because Django Celery workers are single-threaded per process.
    """
    global _twilio_client

    if _twilio_client is not None:
        return _twilio_client

    sid   = getattr(settings, 'TWILIO_ACCOUNT_SID', '')
    token = getattr(settings, 'TWILIO_AUTH_TOKEN', '')

    if not sid or not token:
        logger.warning(
            '[SMS] TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN not configured. '
            'SMS dispatch is disabled.'
        )
        return None

    try:
        from twilio.rest import Client
        _twilio_client = Client(sid, token)
        logger.info('[SMS] Twilio client initialised successfully.')
        return _twilio_client
    except ImportError:
        logger.error('[SMS] twilio package not installed. Run: pip install twilio>=8.0')
        return None
    except Exception as exc:
        logger.error(f'[SMS] Failed to initialise Twilio client: {exc}')
        return None


# ─── Core Send Function ───────────────────────────────────────────────────────

def send_sms(to: str, body: str) -> str | None:
    """
    Send an SMS via Twilio.

    Args:
        to   : E.164 phone number, e.g. '+256762038491'
        body : Message text (max 1600 chars; Twilio splits into segments automatically)

    Returns:
        Twilio message SID (str) on success, None on failure.
    """
    client = _get_client()
    if client is None:
        return None

    from_number = getattr(settings, 'TWILIO_PHONE', '')
    if not from_number:
        logger.warning('[SMS] TWILIO_PHONE_NUMBER not configured — cannot send SMS.')
        return None

    if not to or not to.strip():
        logger.warning('[SMS] Recipient phone number is empty — skipping.')
        return None

    try:
        message = client.messages.create(
            body=body,
            from_=from_number,
            to=to,
        )
        logger.info(
            f'[SMS] ✅ Sent to {to} — SID={message.sid} '
            f'Status={message.status}'
        )
        return message.sid

    except Exception as exc:
        # Import locally to avoid hard dependency at module load time
        try:
            from twilio.base.exceptions import TwilioRestException
            if isinstance(exc, TwilioRestException):
                logger.error(
                    f'[SMS] ❌ Twilio error (HTTP {exc.status}, code {exc.code}): {exc.msg}'
                )
                # Surface unrecoverable error codes to callers
                if exc.status in [400, 401, 403]:
                    return None  # Don't retry on auth/format errors
        except ImportError:
            pass
        logger.error(f'[SMS] ❌ Failed to send SMS to {to}: {exc}')
        return None


# ─── Alert Message Builders ───────────────────────────────────────────────────

def build_ari_alert_body(node, reading, ari_result: dict) -> str:
    """Build a human-readable ARI alert SMS body."""
    risk   = ari_result['risk_level'].upper()
    score  = ari_result['ari_score']
    action = ari_result.get('recommended_action', 'Inspect storage immediately')

    lines = [
        f'⚠️ SMART-STUA ALERT [{risk} RISK]',
        f'Node: {node.node_identifier}',
        f'Location: {node.location_label}',
        f'Temperature: {reading.temperature_c:.1f}°C',
        f'Humidity: {reading.humidity_pct:.1f}%',
    ]
    if reading.moisture_pct is not None:
        lines.append(f'Moisture: {reading.moisture_pct:.1f}%')
    lines += [
        f'ARI Score: {score:.1f}/100',
        f'Action: {action}',
        f'Time: {reading.recorded_at.strftime("%Y-%m-%d %H:%M UTC")}',
    ]
    return '\n'.join(lines)


def build_threshold_breach_body(node, reading, breaches: list[str]) -> str:
    """Build a threshold breach SMS body."""
    lines = [
        f'⚠️ THRESHOLD BREACH',
        f'Node: {node.node_identifier}',
        f'Location: {node.location_label}',
    ] + breaches + [
        f'Time: {reading.recorded_at.strftime("%Y-%m-%d %H:%M UTC")}',
    ]
    return '\n'.join(lines)


def build_offline_alert_body(node, last_seen_str: str) -> str:
    """Build a node-offline SMS body."""
    return (
        f'❌ NODE OFFLINE\n'
        f'Node: {node.node_identifier}\n'
        f'Location: {node.location_label}\n'
        f'Status: No reports for >30 minutes\n'
        f'Last Active: {last_seen_str}'
    )


# ─── Convenience Senders ─────────────────────────────────────────────────────

def send_alert_sms(node, reading, ari_result: dict, to: str) -> str | None:
    """Send an ARI-based alert SMS to the given phone number."""
    body = build_ari_alert_body(node, reading, ari_result)
    return send_sms(to=to, body=body)


def send_offline_sms(node, last_seen_str: str, to: str) -> str | None:
    """Send a node-offline SMS to the given phone number."""
    body = build_offline_alert_body(node, last_seen_str)
    return send_sms(to=to, body=body)
