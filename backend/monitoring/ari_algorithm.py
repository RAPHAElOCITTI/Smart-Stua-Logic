"""
Aflatoxin Risk Index (ARI) Algorithm
=====================================
Calculates contamination risk based on environmental conditions optimal
for Aspergillus flavus growth — the primary aflatoxin-producing fungus.

Scientific Basis:
  - Temperature Factor F(T): Gaussian model centered at 30°C optimal growth
  - Humidity Factor F(H): Sigmoid model above 75% RH threshold
  - Duration Factor F(D): Logarithmic accumulation of sustained exposure

Usage:
    from monitoring.ari_algorithm import calculate_ari

    result = calculate_ari(temperature=32.0, humidity=80.0, duration_hours=4.0)
    # Returns: {"ari_score": 74.3, "risk_level": "High", "factors": {...}}
"""

import math
from typing import TypedDict


class ARIFactors(TypedDict):
    temperature_factor: float
    humidity_factor: float
    duration_factor: float


class ARIResult(TypedDict):
    ari_score: float
    risk_level: str
    risk_color: str
    recommended_action: str
    factors: ARIFactors


# ─── Weight Constants ────────────────────────────────────────────────────────
WEIGHT_TEMPERATURE = 0.35
WEIGHT_HUMIDITY    = 0.45
WEIGHT_DURATION    = 0.20

# ─── Temperature Model ───────────────────────────────────────────────────────
# A. flavus grows optimally 25–35°C, peak ≈ 30°C; negligible below 10°C or above 45°C
TEMP_OPTIMAL   = 30.0   # °C
TEMP_SPREAD    = 5.0    # σ for Gaussian width
TEMP_MIN_GROW  = 10.0   # °C below which growth is negligible
TEMP_MAX_GROW  = 45.0   # °C above which growth is negligible

# ─── Humidity Model ──────────────────────────────────────────────────────────
# Growth requires RH > 70%, accelerates above 85%; below 65% near-zero risk
HUM_INFLECTION = 75.0   # Sigmoid inflection point (%)
HUM_STEEPNESS  = 0.30   # Sigmoid steepness parameter
HUM_MIN_RISK   = 65.0   # Below this, near-zero aflatoxin risk

# ─── Duration Model ──────────────────────────────────────────────────────────
# Logarithmic accumulation; 6h = base unit; max multiplier capped at 2.0
DUR_BASE_HOURS = 6.0
DUR_MAX_FACTOR = 2.0    # Maximum duration multiplier cap

# ─── Risk Level Thresholds ──────────────────────────────────────────────────
RISK_MEDIUM_THRESHOLD = 30.0
RISK_HIGH_THRESHOLD   = 70.0


def _temperature_factor(temperature: float) -> float:
    """
    Gaussian temperature factor centred at optimal A. flavus growth temperature.
    Returns 0.0 outside viable growth range, peak 1.0 at 30°C.
    """
    if temperature < TEMP_MIN_GROW or temperature > TEMP_MAX_GROW:
        return 0.0
    return math.exp(-0.5 * ((temperature - TEMP_OPTIMAL) / TEMP_SPREAD) ** 2)


def _humidity_factor(humidity: float) -> float:
    """
    Sigmoid humidity factor; near-zero below 65% RH, approaches 1.0 above ~90%.
    """
    if humidity < HUM_MIN_RISK:
        return 0.0
    return 1.0 / (1.0 + math.exp(-HUM_STEEPNESS * (humidity - HUM_INFLECTION)))


def _duration_factor(duration_hours: float) -> float:
    """
    Logarithmic duration factor capturing cumulative risk exposure.
    F(D) = log₂(1 + D/6), capped at DUR_MAX_FACTOR.
    """
    if duration_hours <= 0:
        return 0.0
    raw = math.log2(1.0 + duration_hours / DUR_BASE_HOURS)
    return min(raw, DUR_MAX_FACTOR)


def _classify_risk(ari_score: float) -> tuple[str, str, str]:
    """
    Returns (risk_level, risk_color, recommended_action) for a given ARI score.
    """
    if ari_score >= RISK_HIGH_THRESHOLD:
        return (
            'High',
            '#FF3B30',  # Red
            'CRITICAL: Activate grain dryer immediately. Send urgent SMS to farmer and store manager.',
        )
    elif ari_score >= RISK_MEDIUM_THRESHOLD:
        return (
            'Medium',
            '#FF9500',  # Amber
            'WARNING: Monitor closely. Send advisory SMS. Consider ventilation.',
        )
    else:
        return (
            'Low',
            '#34C759',  # Green
            'Normal conditions. Log reading. No immediate action required.',
        )


def calculate_ari(
    temperature: float,
    humidity: float,
    duration_hours: float = 0.0,
) -> ARIResult:
    """
    Calculate Aflatoxin Risk Index for given environmental conditions.

    Args:
        temperature:    Temperature in °C (from DHT22)
        humidity:       Relative humidity percentage (from DHT22)
        duration_hours: Continuous hours under high-risk conditions (default 0)

    Returns:
        ARIResult dict with ari_score (0–100), risk_level, risk_color,
        recommended_action, and individual factor breakdown.

    Examples:
        >>> calculate_ari(30.0, 85.0, 8.0)['risk_level']
        'High'
        >>> calculate_ari(15.0, 55.0, 0.0)['risk_level']
        'Low'
        >>> calculate_ari(28.0, 74.0, 3.0)['risk_level']
        'Medium'
    """
    f_t = _temperature_factor(temperature)
    f_h = _humidity_factor(humidity)
    f_d = _duration_factor(duration_hours)

    raw_score = WEIGHT_TEMPERATURE * f_t + WEIGHT_HUMIDITY * f_h + WEIGHT_DURATION * (f_d / DUR_MAX_FACTOR)
    ari_score = round(min(100.0, max(0.0, raw_score * 100.0)), 2)

    risk_level, risk_color, recommended_action = _classify_risk(ari_score)

    return ARIResult(
        ari_score=ari_score,
        risk_level=risk_level,
        risk_color=risk_color,
        recommended_action=recommended_action,
        factors=ARIFactors(
            temperature_factor=round(f_t, 4),
            humidity_factor=round(f_h, 4),
            duration_factor=round(f_d, 4),
        ),
    )


def get_risk_summary(ari_score: float) -> dict:
    """Quick helper for just risk classification without full calculation."""
    risk_level, risk_color, action = _classify_risk(ari_score)
    return {
        'risk_level': risk_level,
        'risk_color': risk_color,
        'recommended_action': action,
    }


# ─── Boundary Test Values (for verification) ────────────────────────────────
BOUNDARY_TEST_CASES = [
    # (temp, humidity, duration, expected_risk)
    (10.0,  65.0,  0.0, 'Low'),     # At minimum viable growth boundary
    (30.0,  85.0,  8.0, 'High'),    # Optimal aflatoxin conditions
    (25.0,  74.0,  3.0, 'Medium'),  # Mild risk zone
    (15.0,  55.0,  0.0, 'Low'),     # Safe cold dry storage
    (35.0,  90.0, 12.0, 'High'),    # Extreme risk
    (20.0,  70.0,  6.0, 'Low'),     # Moderate conditions, low risk under current weights
]
