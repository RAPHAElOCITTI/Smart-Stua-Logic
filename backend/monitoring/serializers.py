"""
DRF Serializers for Smart-Stua monitoring app.
Covers all 5 models + SensorPayloadSerializer for incoming GSM node JSON.
"""

from django.conf import settings
from django.utils import timezone
from rest_framework import serializers
from .models import User, SensorNode, Reading, AlertLog, Threshold, DryerCommand


# ─── User ─────────────────────────────────────────────────────────────────────
class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model  = User
        fields = ['user_id', 'full_name', 'phone_number', 'email', 'role',
                  'created_at', 'is_active']
        read_only_fields = ['user_id', 'created_at']


class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model  = User
        fields = ['full_name', 'phone_number', 'email', 'role', 'password']

    def create(self, validated_data):
        from django.contrib.auth.hashers import make_password
        validated_data['password_hash'] = make_password(validated_data.pop('password'))
        return User.objects.create(**validated_data)


# ─── SensorNode ───────────────────────────────────────────────────────────────
class SensorNodeSerializer(serializers.ModelSerializer):
    latest_ari = serializers.SerializerMethodField()
    is_online   = serializers.SerializerMethodField()

    class Meta:
        model  = SensorNode
        fields = ['node_id', 'node_identifier', 'location_label', 'mac_address',
                  'gateway_id', 'api_key', 'status', 'last_reading_at', 'is_online',
                  'pending_command', 'installed_at', 'notes', 'latest_ari']
        read_only_fields = ['node_id', 'api_key', 'last_reading_at', 'installed_at', 'is_online']

    def get_is_online(self, obj):
        """True if the node has sent a reading within the last 2 minutes."""
        if not obj.last_reading_at:
            return False
        return (timezone.now() - obj.last_reading_at).total_seconds() < 120

    def get_latest_ari(self, obj):
        """Include latest ARI score in node listing response."""
        try:
            latest = obj.readings.select_related().first()
            if latest and hasattr(latest, 'alert'):
                return {
                    'ari_value': latest.alert.ari_value,
                    'risk_level': latest.alert.risk_level,
                }
        except Exception:
            pass
        return None


# ─── Reading ──────────────────────────────────────────────────────────────────
class ReadingSerializer(serializers.ModelSerializer):
    node_identifier = serializers.CharField(source='node.node_identifier', read_only=True)

    class Meta:
        model  = Reading
        fields = ['reading_id', 'node', 'node_identifier', 'temperature_c',
                  'humidity_pct', 'moisture_pct', 'recorded_at', 'device_ts']
        read_only_fields = ['reading_id', 'recorded_at', 'node_identifier']


# ─── AlertLog ─────────────────────────────────────────────────────────────────
class AlertLogSerializer(serializers.ModelSerializer):
    node_identifier    = serializers.CharField(source='node.node_identifier', read_only=True)
    node_location      = serializers.CharField(source='node.location_label', read_only=True)

    class Meta:
        model  = AlertLog
        fields = ['alert_id', 'node', 'node_identifier', 'node_location',
                  'reading', 'ari_value', 'alert_type', 'risk_level', 'message',
                  'sent_to', 'sent_at', 'action_taken', 'sms_sid']
        read_only_fields = ['alert_id', 'sent_at', 'sms_sid',
                            'node_identifier', 'node_location']


# ─── Threshold ────────────────────────────────────────────────────────────────
class ThresholdSerializer(serializers.ModelSerializer):
    node_identifier = serializers.CharField(source='node.node_identifier', read_only=True)

    class Meta:
        model  = Threshold
        fields = ['threshold_id', 'node', 'node_identifier', 'min_temp',
                  'max_temp', 'min_humidity', 'max_humidity',
                  'risk_duration', 'updated_at']
        read_only_fields = ['threshold_id', 'updated_at', 'node_identifier']

    def validate(self, data):
        if data.get('min_temp', 0) >= data.get('max_temp', 100):
            raise serializers.ValidationError('min_temp must be less than max_temp.')
        if data.get('min_humidity', 0) >= data.get('max_humidity', 100):
            raise serializers.ValidationError('min_humidity must be less than max_humidity.')
        return data


# ─── Sensor Payload (Wi-Fi node → API) ────────────────────────────────────
class SensorPayloadSerializer(serializers.Serializer):
    """
    Validates incoming JSON from ESP32 Wi-Fi/Ethernet nodes.
    Full payload example:
      {
        "node_id":      "NODE_001",
        "temperature":  28.5,
        "humidity":     72.3,
        "moisture_pct": 41.2,
        "api_key":      "<per-node-64-char-hex>"
      }
    Auth: validated against the per-node SensorNode.api_key.
    """
    node_id      = serializers.CharField(max_length=50)
    temperature  = serializers.FloatField(min_value=-40.0, max_value=80.0)
    humidity     = serializers.FloatField(min_value=0.0, max_value=100.0)
    moisture_pct = serializers.FloatField(min_value=0.0, max_value=100.0,
                                          required=False, allow_null=True)
    api_key      = serializers.CharField(max_length=200)
    device_ts    = serializers.DateTimeField(required=False, allow_null=True)

    def validate(self, data):
        """Cross-field validation: check node exists then verify its api_key."""
        node_id = data.get('node_id')
        api_key = data.get('api_key')

        try:
            node = SensorNode.objects.get(node_identifier=node_id, status='active')
        except SensorNode.DoesNotExist:
            raise serializers.ValidationError(
                {'node_id': f'Node "{node_id}" not found or not active.'}
            )

        # Per-node key check (timing-safe comparison)
        import hmac
        if not hmac.compare_digest(node.api_key, api_key):
            raise serializers.ValidationError(
                {'api_key': 'Invalid API key for this node.'}
            )

        # Stash resolved node so view doesn't need a second DB hit
        data['_node'] = node
        return data


# ─── Node Registration (dashboard → API) ──────────────────────────────────────────────────
class NodeRegistrationSerializer(serializers.ModelSerializer):
    """
    Used by POST /api/devices/register/ — lets dashboard users register
    a new node without touching the admin panel or code.
    api_key and provisioning are returned once on creation (read_only thereafter).
    The node's owner is set to request.user by the view (not from request body).
    """
    api_key      = serializers.CharField(read_only=True)
    provisioning = serializers.SerializerMethodField()

    class Meta:
        model  = SensorNode
        fields = ['node_id', 'node_identifier', 'location_label',
                  'mac_address', 'notes', 'api_key', 'provisioning']
        read_only_fields = ['node_id', 'api_key']

    def create(self, validated_data):
        """Owner is injected by the view via serializer.save(owner=user_obj)."""
        return SensorNode.objects.create(**validated_data)

    def get_provisioning(self, obj):
        """Return everything a device needs to connect, shown once on registration."""
        mqtt_host = getattr(settings, 'MQTT_BROKER', 'localhost')
        mqtt_port = getattr(settings, 'MQTT_PORT', 1883)
        return {
            'mqtt_broker': mqtt_host,
            'mqtt_port': mqtt_port,
            'mqtt_topic': f'nodes/{obj.node_identifier}/telemetry',
            'http_endpoint': 'POST /api/readings/',
            'payload_schema': {
                'node_id': obj.node_identifier,
                'temperature': 0.0,
                'humidity': 0.0,
                'moisture_pct': 0.0,
                'api_key': obj.api_key,
            },
        }


# ─── Dashboard Summary ────────────────────────────────────────────────────────
class DashboardNodeSummarySerializer(serializers.Serializer):
    """Per-node summary for the /api/dashboard/summary/ endpoint."""
    node_id         = serializers.IntegerField()
    node_identifier = serializers.CharField()
    location_label  = serializers.CharField()
    status          = serializers.CharField()
    last_reading_at = serializers.DateTimeField(allow_null=True)
    temperature_c   = serializers.FloatField(allow_null=True)
    humidity_pct    = serializers.FloatField(allow_null=True)
    moisture_pct    = serializers.FloatField(allow_null=True)   # ← Feature 1 fix
    ari_value       = serializers.FloatField(allow_null=True)
    risk_level      = serializers.CharField(allow_null=True)
    risk_color      = serializers.CharField(allow_null=True)
    dryer_active    = serializers.BooleanField()
    pending_command = serializers.CharField()


# ─── Dryer Command ────────────────────────────────────────────────────────────
class DryerCommandSerializer(serializers.Serializer):
    """Dryer command response for ESP32 polling."""
    command = serializers.ChoiceField(choices=DryerCommand.choices)
