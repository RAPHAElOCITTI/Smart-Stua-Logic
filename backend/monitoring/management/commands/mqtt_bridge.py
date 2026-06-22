import json
import logging
import os
import ssl
import time

from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
from monitoring.models import SensorNode, Reading
from monitoring.serializers import SensorPayloadSerializer
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Starts the MQTT-to-Django database bridge daemon (supports plain + TLS).'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting Smart-Stua MQTT Bridge...'))

        client = mqtt.Client(
            client_id='smartstua_django_bridge',
            clean_session=False,
            protocol=mqtt.MQTTv311,
        )

        # Configure username/password if specified in settings
        if getattr(settings, 'MQTT_USERNAME', '') and getattr(settings, 'MQTT_PASSWORD', ''):
            client.username_pw_set(settings.MQTT_USERNAME, settings.MQTT_PASSWORD)
            logger.info('MQTT Authentication configured.')

        # ── TLS / SSL (required for HiveMQ Cloud port 8883) ─────────────────
        broker_port = int(getattr(settings, 'MQTT_PORT', 1883))
        use_tls = os.environ.get('MQTT_USE_TLS', '').lower() in ('1', 'true', 'yes') or broker_port == 8883

        if use_tls:
            try:
                import certifi
                ca_bundle = certifi.where()
            except ImportError:
                ca_bundle = None  # Use system default CA store

            client.tls_set(
                ca_certs=ca_bundle,
                certfile=None,
                keyfile=None,
                cert_reqs=ssl.CERT_REQUIRED,
                tls_version=ssl.PROTOCOL_TLS_CLIENT,
            )
            client.tls_insecure_set(False)  # Enforce cert verification in production
            logger.info(f'TLS enabled (CA: {ca_bundle or "system default"})')

        # Set up callbacks
        client.on_connect = self.on_connect
        client.on_disconnect = self.on_disconnect
        client.on_message = self.on_message

        broker_host = getattr(settings, 'MQTT_BROKER', 'localhost')

        self.stdout.write(f'Connecting to broker at {broker_host}:{broker_port} (TLS={use_tls})...')

        while True:
            try:
                client.connect(broker_host, broker_port, keepalive=60)
                break
            except Exception as e:
                logger.error(f'Failed to connect to broker ({e}). Retrying in 5s...')
                time.sleep(5)

        # Start the loop (handles reconnection automatically)
        client.loop_forever()


    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.stdout.write(self.style.SUCCESS('Connected to MQTT Broker successfully!'))
            # Subscribe to the telemetry topic wildcard
            # Payloads are expected on: nodes/<node_id>/telemetry
            topic = "nodes/+/telemetry"
            client.subscribe(topic, qos=1)
            logger.info(f"Subscribed to topic: {topic}")
        else:
            logger.error(f"Connection failed with code {rc}")

    def on_disconnect(self, client, userdata, rc):
        logger.warning(f"Disconnected from MQTT broker. Result code: {rc}")

    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload_str = msg.payload.decode('utf-8', errors='ignore')
        logger.info(f"Received MQTT message on topic '{topic}': {payload_str}")

        try:
            data = json.loads(payload_str)
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON payload received on topic {topic}")
            return

        # Use the serializer to validate the node, api_key, and sensor data
        serializer = SensorPayloadSerializer(data=data)
        if not serializer.is_valid():
            logger.warning(f"MQTT validation failed: {serializer.errors}")
            # Optionally publish an error back to the node
            # client.publish(f"nodes/{data.get('node_id')}/errors", json.dumps(serializer.errors))
            return

        # Validation success: get the stashed node and clean data
        validated_data = serializer.validated_data
        node = validated_data['_node']

        try:
            # 1. Create reading record
            reading = Reading.objects.create(
                node=node,
                temperature_c=validated_data['temperature'],
                humidity_pct=validated_data['humidity'],
                moisture_pct=validated_data.get('moisture_pct'),  # optional
                device_ts=validated_data.get('device_ts')
            )

            # 2. Update last active timestamp on node
            node.last_reading_at = timezone.now()
            node.save(update_fields=['last_reading_at'])

            # 3. Queue Celery task for ARI calculation, risk escalation, and notifications
            from monitoring.tasks import process_sensor_data
            process_sensor_data.delay(reading.reading_id)

            logger.info(
                f"Successfully bridged reading from MQTT: node={node.node_identifier}, "
                f"T={reading.temperature_c}°C, H={reading.humidity_pct}%, reading_id={reading.reading_id}"
            )
        except Exception as e:
            logger.error(f"Error persisting MQTT reading to database: {e}", exc_info=True)
