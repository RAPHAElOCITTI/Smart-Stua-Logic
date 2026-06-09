"""
DRF Serializers for Smart-Stua monitoring app.
Covers all 5 models + SensorPayloadSerializer for incoming GSM node JSON.
"""

from django.conf import settings
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

    class Meta:
        model  = SensorNode
        fields = ['node_id', 'node_identifier', 'location_label', 'gateway_id',
                  'status', 'last_reading_at', 'pending_command',
                  'installed_at', 'notes', 'latest_ari']
        read_only_fields = ['node_id', 'last_reading_at', 'installed_at']

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
                  'humidity_pct', 'recorded_at', 'device_ts']
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


# ─── Sensor Payload (GSM node → API) ─────────────────────────────────────────
class SensorPayloadSerializer(serializers.Serializer):
    """
    Validates incoming JSON from ESP32+SIM800L nodes.
    Format: {"node_id": "NODE_001", "temperature": 28.5, "humidity": 72.3, "api_key": "xxx"}
    """
    node_id     = serializers.CharField(max_length=50)
    temperature = serializers.FloatField(min_value=-40.0, max_value=80.0)
    humidity    = serializers.FloatField(min_value=0.0, max_value=100.0)
    api_key     = serializers.CharField(max_length=200)
    device_ts   = serializers.DateTimeField(required=False, allow_null=True)

    def validate_api_key(self, value):
        if value != settings.SENSOR_API_KEY:
            raise serializers.ValidationError('Invalid API key.')
        return value

    def validate_node_id(self, value):
        if not SensorNode.objects.filter(node_identifier=value,
                                          status='active').exists():
            raise serializers.ValidationError(
                f'Node "{value}" not found or not active.'
            )
        return value


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
    ari_value       = serializers.FloatField(allow_null=True)
    risk_level      = serializers.CharField(allow_null=True)
    risk_color      = serializers.CharField(allow_null=True)
    dryer_active    = serializers.BooleanField()
    pending_command = serializers.CharField()


# ─── Dryer Command ────────────────────────────────────────────────────────────
class DryerCommandSerializer(serializers.Serializer):
    """Dryer command response for ESP32 polling."""
    command = serializers.ChoiceField(choices=DryerCommand.choices)
