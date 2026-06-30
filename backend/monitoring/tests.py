"""
Unit tests for Smart-Stua monitoring — ARI algorithm + API endpoints.
Run with: python manage.py test monitoring
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from .ari_algorithm import (
    calculate_ari, BOUNDARY_TEST_CASES,
    MOIST_SAFE_PCT, MOIST_CRITICAL_PCT, MOIST_OVERRIDE_PCT, MOIST_OVERRIDE_FLOOR,
)
from .models import SensorNode, Reading, Threshold, NodeStatus


# ─── ARI Algorithm Tests ──────────────────────────────────────────────────────
class ARIAlgorithmTestCase(TestCase):
    """Verify ARI calculation at boundary values (ARI 30 and 70)."""

    def test_low_risk_cold_dry(self):
        """Cold dry storage, safe moisture → Low risk."""
        result = calculate_ari(15.0, 50.0, moisture_pct=12.0, duration_hours=0.0)
        self.assertEqual(result['risk_level'], 'Low')
        self.assertLess(result['ari_score'], 30.0)

    def test_medium_risk_warm_moderate(self):
        """Warm moderate humidity, safe moisture → Medium risk."""
        result = calculate_ari(28.0, 74.0, moisture_pct=12.0, duration_hours=3.0)
        self.assertGreaterEqual(result['ari_score'], 30.0)
        self.assertLess(result['ari_score'], 70.0)
        self.assertEqual(result['risk_level'], 'Medium')

    def test_high_risk_optimal_conditions(self):
        """Optimal A. flavus conditions + unsafe moisture → High risk."""
        result = calculate_ari(30.0, 85.0, moisture_pct=14.8, duration_hours=8.0)
        self.assertGreaterEqual(result['ari_score'], 70.0)
        self.assertEqual(result['risk_level'], 'High')

    def test_boundary_low_to_medium_at_30(self):
        """ARI score exactly at boundary (≥30 → Medium)."""
        result = calculate_ari(30.0, 80.0, moisture_pct=None, duration_hours=0.0)
        self.assertIn(result['risk_level'], ['Medium', 'High'])

    def test_boundary_medium_to_high_at_70(self):
        """ARI score reaches High threshold with combined extreme conditions + moisture."""
        # Under the 4-factor formula (T=0.25, H=0.30, M=0.30, D=0.15),
        # reaching >= 70 requires moisture contribution.  This tests the
        # legitimate formula path (not the override), using clearly critical MC.
        result = calculate_ari(30.0, 90.0, moisture_pct=16.0, duration_hours=12.0)
        self.assertGreaterEqual(result['ari_score'], 70.0)
        self.assertEqual(result['risk_level'], 'High')

    def test_extreme_temperature_below_range(self):
        """Temperature below 10°C → near-zero temperature factor."""
        result = calculate_ari(5.0, 85.0, moisture_pct=None, duration_hours=0.0)
        # Temperature factor = 0, risk should be low/medium based on humidity alone
        self.assertLessEqual(result['factors']['temperature_factor'], 0.01)

    def test_extreme_temperature_above_range(self):
        """Temperature above 45°C → near-zero temperature factor."""
        result = calculate_ari(50.0, 85.0, moisture_pct=None, duration_hours=0.0)
        self.assertLessEqual(result['factors']['temperature_factor'], 0.01)

    def test_low_humidity_below_65(self):
        """Humidity below 65% → near-zero humidity factor."""
        result = calculate_ari(30.0, 60.0, moisture_pct=None, duration_hours=0.0)
        self.assertLessEqual(result['factors']['humidity_factor'], 0.01)

    def test_ari_score_range_0_to_100(self):
        """ARI score must always be between 0 and 100."""
        test_cases = [
            (0.0,   0.0,  None,  0.0),
            (30.0, 85.0,  14.8, 100.0),
            (100.0, 100.0, 20.0, 1000.0),
            (-20.0, -10.0, None, 0.0),
        ]
        for temp, hum, moist, dur in test_cases:
            result = calculate_ari(temp, hum, moisture_pct=moist, duration_hours=dur)
            self.assertGreaterEqual(result['ari_score'], 0.0)
            self.assertLessEqual(result['ari_score'], 100.0)

    def test_boundary_test_cases_from_algorithm(self):
        """Run all predefined boundary test cases (now 5-tuple with moisture_pct)."""
        for temp, hum, moist, dur, expected_risk in BOUNDARY_TEST_CASES:
            with self.subTest(temp=temp, hum=hum, moist=moist, dur=dur):
                result = calculate_ari(temp, hum, moisture_pct=moist, duration_hours=dur)
                self.assertEqual(
                    result['risk_level'], expected_risk,
                    f'Expected {expected_risk} but got {result["risk_level"]} '
                    f'(ARI={result["ari_score"]}) for T={temp} H={hum} MC={moist} D={dur}'
                )

    def test_duration_factor_accumulation(self):
        """Longer duration → higher ARI score."""
        result_0h  = calculate_ari(28.0, 75.0, moisture_pct=None, duration_hours=0.0)
        result_6h  = calculate_ari(28.0, 75.0, moisture_pct=None, duration_hours=6.0)
        result_12h = calculate_ari(28.0, 75.0, moisture_pct=None, duration_hours=12.0)
        self.assertLessEqual(result_0h['ari_score'], result_6h['ari_score'])
        self.assertLessEqual(result_6h['ari_score'], result_12h['ari_score'])

    def test_result_has_required_fields(self):
        """Result dict must contain all required fields including new moisture fields."""
        result = calculate_ari(25.0, 75.0, moisture_pct=12.0, duration_hours=2.0)
        self.assertIn('ari_score', result)
        self.assertIn('risk_level', result)
        self.assertIn('risk_color', result)
        self.assertIn('recommended_action', result)
        self.assertIn('moisture_override', result)
        self.assertIn('factors', result)
        self.assertIn('temperature_factor', result['factors'])
        self.assertIn('humidity_factor', result['factors'])
        self.assertIn('moisture_factor', result['factors'])
        self.assertIn('duration_factor', result['factors'])

    # ─── Moisture Integration Tests ────────────────────────────────────────────────

    def test_safe_moisture_does_not_inflate_ari(self):
        """
        Moisture <= 13.5% (safe storage limit) must contribute F(M)=0,
        so ARI should match a no-moisture call for the same T/H/D inputs.
        """
        result_no_moist  = calculate_ari(20.0, 68.0, moisture_pct=None,  duration_hours=0.0)
        result_safe_moist = calculate_ari(20.0, 68.0, moisture_pct=12.0, duration_hours=0.0)
        self.assertEqual(
            result_no_moist['ari_score'],
            result_safe_moist['ari_score'],
            'Safe moisture should produce same ARI as no-moisture reading',
        )
        self.assertAlmostEqual(result_safe_moist['factors']['moisture_factor'], 0.0, places=4)
        self.assertFalse(result_safe_moist['moisture_override'])

    def test_unsafe_moisture_forces_high_risk_override(self):
        """
        Moisture >= 14.5% must unconditionally raise ARI to at least 70.0
        (High Risk), even in otherwise-safe cold and dry conditions.
        This is the critical safety override for the grain dryer trigger.
        """
        # Conditions that would normally produce Low risk:
        result = calculate_ari(15.0, 50.0, moisture_pct=14.8, duration_hours=0.0)
        self.assertGreaterEqual(
            result['ari_score'], MOIST_OVERRIDE_FLOOR,
            f'Expected ARI >= {MOIST_OVERRIDE_FLOOR}, got {result["ari_score"]}',
        )
        self.assertEqual(result['risk_level'], 'High')
        self.assertTrue(
            result['moisture_override'],
            'moisture_override flag must be True when safety floor was applied',
        )

    def test_moisture_factor_linear_scaling(self):
        """
        F(M) must scale linearly from 0.0 at 13.5% to 1.0 at 15.0%.
        Validates the ramp: F(M) = (MC - 13.5) / (15.0 - 13.5)
        """
        # Mid-point: (13.5 + 15.0) / 2 = 14.25%  → F(M) should be 0.5
        result_mid = calculate_ari(15.0, 50.0, moisture_pct=14.25, duration_hours=0.0)
        self.assertAlmostEqual(
            result_mid['factors']['moisture_factor'], 0.5, places=3,
            msg='F(M) at midpoint (14.25%) should be ~0.5',
        )

        # Quarter-point: 13.5 + 0.375 = 13.875%  → F(M) should be 0.25
        result_qtr = calculate_ari(15.0, 50.0, moisture_pct=13.875, duration_hours=0.0)
        self.assertAlmostEqual(
            result_qtr['factors']['moisture_factor'], 0.25, places=3,
            msg='F(M) at quarter-point (13.875%) should be ~0.25',
        )

        # At lower safe boundary: 13.5%  → F(M) should be exactly 0.0
        result_safe = calculate_ari(15.0, 50.0, moisture_pct=MOIST_SAFE_PCT, duration_hours=0.0)
        self.assertAlmostEqual(result_safe['factors']['moisture_factor'], 0.0, places=4)

        # At critical ceiling: 15.0%  → F(M) should be exactly 1.0
        result_crit = calculate_ari(15.0, 50.0, moisture_pct=MOIST_CRITICAL_PCT, duration_hours=0.0)
        self.assertAlmostEqual(result_crit['factors']['moisture_factor'], 1.0, places=4)

    def test_moisture_override_boundary_exact(self):
        """
        moisture_pct == MOIST_OVERRIDE_PCT (14.5) must fire the override.
        moisture_pct just below (14.49) must NOT fire the override.
        """
        at_boundary = calculate_ari(15.0, 50.0, moisture_pct=MOIST_OVERRIDE_PCT, duration_hours=0.0)
        # 14.5% may or may not produce ARI >= 70 by formula alone; the flag matters
        self.assertGreaterEqual(at_boundary['ari_score'], MOIST_OVERRIDE_FLOOR)
        self.assertEqual(at_boundary['risk_level'], 'High')

        below_boundary = calculate_ari(15.0, 50.0, moisture_pct=14.49, duration_hours=0.0)
        self.assertFalse(
            below_boundary['moisture_override'],
            '14.49% MC should NOT trigger the safety override',
        )


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
            api_key=self.api_key,
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
