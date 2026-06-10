"""
Smart-Stua monitoring app — Django models.

Matches the ER diagram exactly:
  Users, SensorNodes, Readings, AlertLogs, Thresholds
"""

import secrets
from django.db import models
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone


class UserRole(models.TextChoices):
    FARMER        = 'farmer',        'Farmer'
    STORE_MANAGER = 'store_manager', 'Store Manager'
    ADMIN         = 'admin',         'System Admin'


class NodeStatus(models.TextChoices):
    ACTIVE      = 'active',      'Active'
    INACTIVE    = 'inactive',    'Inactive'
    MAINTENANCE = 'maintenance', 'Maintenance'


class RiskLevel(models.TextChoices):
    LOW    = 'Low',    'Low'
    MEDIUM = 'Medium', 'Medium'
    HIGH   = 'High',   'High'


class DryerCommand(models.TextChoices):
    ON   = 'ON',   'Turn On'
    OFF  = 'OFF',  'Turn Off'
    NONE = 'NONE', 'No Command'


class AlertType(models.TextChoices):
    ARI_RISK         = 'ari_risk',         'ARI Risk'
    THRESHOLD_BREACH = 'threshold_breach', 'Threshold Breach'
    NODE_OFFLINE     = 'node_offline',     'Node Offline'


# ─── User ─────────────────────────────────────────────────────────────────────
class User(models.Model):
    """System users with role-based access (Farmer / Store Manager / Admin)."""

    user_id      = models.AutoField(primary_key=True)
    full_name    = models.CharField(max_length=200)
    phone_number = models.CharField(max_length=20, unique=True)
    email        = models.EmailField(unique=True, blank=True, null=True)
    role         = models.CharField(max_length=20, choices=UserRole.choices,
                                    default=UserRole.FARMER)
    password_hash = models.CharField(max_length=255)
    created_at   = models.DateTimeField(default=timezone.now)
    is_active    = models.BooleanField(default=True)
    push_token   = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = 'users'
        ordering = ['full_name']

    def __str__(self):
        return f'{self.full_name} ({self.role})'


# ─── SensorNode ───────────────────────────────────────────────────────────────
class SensorNode(models.Model):
    """Registered Wi-Fi/Ethernet ESP32 sensor nodes deployed in grain storage."""

    node_id         = models.AutoField(primary_key=True)
    node_identifier = models.CharField(
        max_length=50, unique=True,
        help_text='Human-readable node ID, e.g. NODE_001'
    )
    location_label  = models.CharField(
        max_length=200,
        help_text='Physical location, e.g. Gulu Main Store — Section A'
    )
    mac_address     = models.CharField(
        max_length=17, blank=True, null=True,
        help_text='Node Wi-Fi/Ethernet MAC address (AA:BB:CC:DD:EE:FF)'
    )
    # Kept for backwards compatibility; was GSM gateway ID.
    gateway_id      = models.CharField(
        max_length=100, blank=True, null=True,
        help_text='Legacy field — use mac_address for new Wi-Fi nodes'
    )
    # Per-node secret key — auto-generated on creation, used to authenticate
    # MQTT payloads and HTTP POST /api/readings/ requests.
    api_key         = models.CharField(
        max_length=64, unique=True, blank=True,
        help_text='Auto-generated per-node secret key (do not share publicly)'
    )
    status          = models.CharField(
        max_length=20, choices=NodeStatus.choices,
        default=NodeStatus.ACTIVE
    )
    last_reading_at = models.DateTimeField(blank=True, null=True)
    pending_command = models.CharField(
        max_length=10, choices=DryerCommand.choices,
        default=DryerCommand.NONE
    )
    installed_at    = models.DateTimeField(default=timezone.now)
    notes           = models.TextField(blank=True)

    class Meta:
        db_table = 'sensor_nodes'
        ordering = ['location_label']

    def __str__(self):
        return f'{self.node_identifier} — {self.location_label}'

    def rotate_api_key(self):
        """Regenerate the per-node API key (call when a key is compromised)."""
        self.api_key = secrets.token_hex(32)
        self.save(update_fields=['api_key'])
        return self.api_key


@receiver(pre_save, sender=SensorNode)
def _auto_generate_api_key(sender, instance, **kwargs):
    """Auto-generate a unique API key when a new SensorNode is saved without one."""
    if not instance.api_key:
        instance.api_key = secrets.token_hex(32)


# ─── Reading ──────────────────────────────────────────────────────────────────
class Reading(models.Model):
    """Raw sensor data transmitted from Wi-Fi/Ethernet nodes."""

    reading_id    = models.BigAutoField(primary_key=True)
    node          = models.ForeignKey(SensorNode, on_delete=models.CASCADE,
                                       related_name='readings', db_column='node_id')
    temperature_c = models.FloatField(help_text='Temperature in °C from DHT22')
    humidity_pct  = models.FloatField(help_text='Relative humidity % from DHT22')
    moisture_pct  = models.FloatField(
        null=True, blank=True,
        help_text='Grain/soil moisture % from capacitive sensor (ESP32 ADC pin 34)'
    )
    recorded_at   = models.DateTimeField(default=timezone.now,
                                          help_text='Server receipt timestamp')
    device_ts     = models.DateTimeField(blank=True, null=True,
                                          help_text='Timestamp from device (if provided)')

    class Meta:
        db_table  = 'readings'
        ordering  = ['-recorded_at']
        indexes   = [
            models.Index(fields=['node', '-recorded_at']),
        ]

    def __str__(self):
        return (f'[{self.node.node_identifier}] '
                f'{self.temperature_c}°C / {self.humidity_pct}% '
                f'@ {self.recorded_at:%Y-%m-%d %H:%M}')


# ─── AlertLog ─────────────────────────────────────────────────────────────────
class AlertLog(models.Model):
    """Alert history with computed ARI scores — generated by Celery tasks."""

    alert_id     = models.AutoField(primary_key=True)
    node         = models.ForeignKey(SensorNode, on_delete=models.CASCADE,
                                      related_name='alerts', db_column='node_id')
    reading      = models.OneToOneField(Reading, on_delete=models.CASCADE,
                                         related_name='alert', db_column='reading_id',
                                         null=True, blank=True)
    ari_value    = models.FloatField(null=True, blank=True, help_text='Computed ARI score 0–100')
    alert_type   = models.CharField(max_length=20, choices=AlertType.choices,
                                    default=AlertType.ARI_RISK)
    risk_level   = models.CharField(max_length=10, choices=RiskLevel.choices)
    message      = models.TextField(help_text='Alert message body')
    sent_to      = models.CharField(max_length=255,
                                     help_text='Phone number or email alert was sent to')
    sent_at      = models.DateTimeField(default=timezone.now)
    action_taken = models.BooleanField(default=False,
                                        help_text='Has the farmer acknowledged/acted?')
    sms_sid      = models.CharField(max_length=100, blank=True,
                                     help_text='Twilio message SID for delivery tracking')

    class Meta:
        db_table = 'alert_logs'
        ordering = ['-sent_at']
        indexes  = [
            models.Index(fields=['node', '-sent_at']),
            models.Index(fields=['risk_level']),
        ]

    def __str__(self):
        return (f'[{self.risk_level}] ARI={self.ari_value:.1f} '
                f'Node={self.node.node_identifier} '
                f'@ {self.sent_at:%Y-%m-%d %H:%M}')


# ─── Threshold ────────────────────────────────────────────────────────────────
class Threshold(models.Model):
    """Per-node configurable alert thresholds — set by Store Manager / Admin."""

    threshold_id   = models.AutoField(primary_key=True)
    node           = models.OneToOneField(SensorNode, on_delete=models.CASCADE,
                                           related_name='threshold', db_column='node_id')
    min_temp       = models.FloatField(default=10.0,
                                        help_text='Minimum temperature (°C) — alert below this')
    max_temp       = models.FloatField(default=35.0,
                                        help_text='Maximum temperature (°C) — alert above this')
    min_humidity   = models.FloatField(default=40.0,
                                        help_text='Minimum humidity (%) — alert below this')
    max_humidity   = models.FloatField(default=75.0,
                                        help_text='Maximum humidity (%) — alert above this')
    risk_duration  = models.IntegerField(default=6,
                                          help_text='Hours of sustained risk before escalation')
    updated_at     = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'thresholds'

    def __str__(self):
        return (f'Thresholds for {self.node.node_identifier}: '
                f'T={self.min_temp}–{self.max_temp}°C, '
                f'H={self.min_humidity}–{self.max_humidity}%')
