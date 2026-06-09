"""
Unit tests for Smart-Stua monitoring — ARI algorithm + API endpoints.
Run with: python manage.py test monitoring
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from .ari_algorithm import calculate_ari, BOUNDARY_TEST_CASES
from .models import SensorNode, Reading, Threshold, NodeStatus


# ─── ARI Algorithm Tests ──────────────────────────────────────────────────────
class ARIAlgorithmTestCase(TestCase):
    """Verify ARI calculation at boundary values (ARI 30 and 70)."""

    def test_low_risk_cold_dry(self):
        """Cold dry storage → Low risk."""
        result = calculate_ari(15.0, 50.0, 0.0)
        self.assertEqual(result['risk_level'], 'Low')
        self.assertLess(result['ari_score'], 30.0)

    def test_medium_risk_warm_moderate(self):
        """Warm moderate humidity → Medium risk."""
        result = calculate_ari(28.0, 74.0, 3.0)
        self.assertGreaterEqual(result['ari_score'], 30.0)
        self.assertLess(result['ari_score'], 70.0)
        self.assertEqual(result['risk_level'], 'Medium')

    def test_high_risk_optimal_conditions(self):
        """Optimal A. flavus conditions → High risk."""
        result = calculate_ari(30.0, 85.0, 8.0)
        self.assertGreaterEqual(result['ari_score'], 70.0)
        self.assertEqual(result['risk_level'], 'High')

    def test_boundary_low_to_medium_at_30(self):
        """ARI score exactly at boundary (≥30 → Medium)."""
        # These conditions should produce exactly medium or above
        result = calculate_ari(30.0, 80.0, 0.0)
        self.assertIn(result['risk_level'], ['Medium', 'High'])

    def test_boundary_medium_to_high_at_70(self):
        """ARI score at High threshold."""
        result = calculate_ari(30.0, 90.0, 12.0)
        self.assertGreaterEqual(result['ari_score'], 70.0)
        self.assertEqual(result['risk_level'], 'High')

    def test_extreme_temperature_below_range(self):
        """Temperature below 10°C → near-zero temperature factor."""
        result = calculate_ari(5.0, 85.0, 0.0)
        # Temperature factor = 0, risk should be low/medium based on humidity alone
        self.assertLessEqual(result['factors']['temperature_factor'], 0.01)

    def test_extreme_temperature_above_range(self):
        """Temperature above 45°C → near-zero temperature factor."""
        result = calculate_ari(50.0, 85.0, 0.0)
        self.assertLessEqual(result['factors']['temperature_factor'], 0.01)

    def test_low_humidity_below_65(self):
        """Humidity below 65% → near-zero humidity factor."""
        result = calculate_ari(30.0, 60.0, 0.0)
        self.assertLessEqual(result['factors']['humidity_factor'], 0.01)

    def test_ari_score_range_0_to_100(self):
        """ARI score must always be between 0 and 100."""
        test_cases = [
            (0.0, 0.0, 0.0),
            (30.0, 85.0, 100.0),
            (100.0, 100.0, 1000.0),
            (-20.0, -10.0, 0.0),
        ]
        for temp, hum, dur in test_cases:
            result = calculate_ari(temp, hum, dur)
            self.assertGreaterEqual(result['ari_score'], 0.0)
            self.assertLessEqual(result['ari_score'], 100.0)

    def test_boundary_test_cases_from_algorithm(self):
        """Run all predefined boundary test cases."""
        for temp, hum, dur, expected_risk in BOUNDARY_TEST_CASES:
            with self.subTest(temp=temp, hum=hum, dur=dur):
                result = calculate_ari(temp, hum, dur)
                self.assertEqual(
                    result['risk_level'], expected_risk,
                    f'Expected {expected_risk} but got {result["risk_level"]} '
                    f'(ARI={result["ari_score"]}) for T={temp} H={hum} D={dur}'
                )

    def test_duration_factor_accumulation(self):
        """Longer duration → higher ARI score."""
        result_0h  = calculate_ari(28.0, 75.0, 0.0)
        result_6h  = calculate_ari(28.0, 75.0, 6.0)
        result_12h = calculate_ari(28.0, 75.0, 12.0)
        self.assertLessEqual(result_0h['ari_score'], result_6h['ari_score'])
        self.assertLessEqual(result_6h['ari_score'], result_12h['ari_score'])

    def test_result_has_required_fields(self):
        """Result dict must contain all required fields."""
        result = calculate_ari(25.0, 75.0, 2.0)
        self.assertIn('ari_score', result)
        self.assertIn('risk_level', result)
        self.assertIn('risk_color', result)
        self.assertIn('recommended_action', result)
        self.assertIn('factors', result)
        self.assertIn('temperature_factor', result['factors'])
        self.assertIn('humidity_factor', result['factors'])
        self.assertIn('duration_factor', result['factors'])


# ─── API Endpoint Tests ───────────────────────────────────────────────────────
class SensorReadingAPITestCase(TestCase):
    """Test the sensor data ingestion endpoint."""

    def setUp(self):
        from django.conf import settings
        self.client = APIClient()
        self.api_key = getattr(settings, 'SENSOR_API_KEY', 'dev-sensor-api-key')

        self.node = SensorNode.objects.create(
            node_identifier='NODE_001',
            location_label='Test Grain Store - Section A',
            status=NodeStatus.ACTIVE,
        )
        Threshold.objects.create(
            node=self.node,
            min_temp=10.0, max_temp=35.0,
            min_humidity=40.0, max_humidity=75.0,
            risk_duration=6,
        )

    def test_valid_reading_creates_record(self):
        """Valid sensor payload → 201 Created + reading stored."""
        payload = {
            'node_id': 'NODE_001',
            'temperature': 28.5,
            'humidity': 72.3,
            'api_key': self.api_key,
        }
        response = self.client.post('/api/readings/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Reading.objects.filter(node=self.node).count(), 1)
        self.assertIn('reading_id', response.data)

    def test_invalid_api_key_rejected(self):
        """Wrong API key → 400 Bad Request."""
        payload = {
            'node_id': 'NODE_001',
            'temperature': 28.5,
            'humidity': 72.3,
            'api_key': 'wrong-key',
        }
        response = self.client.post('/api/readings/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unknown_node_rejected(self):
        """Unknown node_id → 400 Bad Request."""
        payload = {
            'node_id': 'NODE_999',
            'temperature': 28.5,
            'humidity': 72.3,
            'api_key': self.api_key,
        }
        response = self.client.post('/api/readings/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_temperature_out_of_range_rejected(self):
        """Temperature > 80°C → 400 Bad Request."""
        payload = {
            'node_id': 'NODE_001',
            'temperature': 200.0,  # Invalid
            'humidity': 72.3,
            'api_key': self.api_key,
        }
        response = self.client.post('/api/readings/', payload, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_node_last_reading_updated(self):
        """After successful POST, node.last_reading_at should be updated."""
        payload = {
            'node_id': 'NODE_001',
            'temperature': 28.5,
            'humidity': 72.3,
            'api_key': self.api_key,
        }
        self.client.post('/api/readings/', payload, format='json')
        self.node.refresh_from_db()
        self.assertIsNotNone(self.node.last_reading_at)


# ─── Model Relationship Tests ────────────────────────────────────────────────
class ModelRelationshipTestCase(TestCase):
    """Verify FK constraints match ER diagram."""

    def setUp(self):
        self.node = SensorNode.objects.create(
            node_identifier='NODE_T01',
            location_label='Test Store',
            status=NodeStatus.ACTIVE,
        )

    def test_reading_fk_to_sensor_node(self):
        """Reading.node FK → SensorNode."""
        reading = Reading.objects.create(
            node=self.node,
            temperature_c=25.0,
            humidity_pct=65.0,
        )
        self.assertEqual(reading.node.node_identifier, 'NODE_T01')

    def test_threshold_one_to_one_sensor_node(self):
        """Threshold.node is OneToOne with SensorNode."""
        threshold = Threshold.objects.create(
            node=self.node,
            min_temp=10.0, max_temp=35.0,
            min_humidity=40.0, max_humidity=75.0,
        )
        self.assertEqual(threshold.node.node_id, self.node.node_id)
        # Cannot create duplicate threshold for same node
        from django.db import IntegrityError
        with self.assertRaises(Exception):
            Threshold.objects.create(node=self.node)

    def test_cascade_delete_readings_with_node(self):
        """Deleting SensorNode cascades to Reading records."""
        Reading.objects.create(node=self.node, temperature_c=25.0, humidity_pct=60.0)
        Reading.objects.create(node=self.node, temperature_c=26.0, humidity_pct=61.0)
        self.assertEqual(Reading.objects.filter(node=self.node).count(), 2)
        self.node.delete()
        self.assertEqual(Reading.objects.count(), 0)
