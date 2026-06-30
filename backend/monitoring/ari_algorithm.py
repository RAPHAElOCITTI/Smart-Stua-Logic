"""
Aflatoxin Risk Index (ARI) Algorithm
=====================================
Calculates contamination risk based on environmental conditions optimal
for Aspergillus flavus growth — the primary aflatoxin-producing fungus.

Scientific Basis:
  - Temperature Factor F(T): Gaussian model centered at 30°C optimal growth
  - Humidity Factor F(H): Sigmoid model above 75% RH threshold
  - Moisture Factor F(M): Linear model based on FAO/East African grain storage
                          standards (safe < 13.5% MC, critical >= 15.0% MC)
  - Duration Factor F(D): Logarithmic accumulation of sustained exposure

Safety Override:
  - If grain moisture content >= 14.5%, the ARI score is unconditionally
    clamped to a minimum of 70.0 (High Risk), regardless of T/H readings.
    This reflects real-world practice: high MC alone guarantees mold growth.

Usage:
    from monitoring.ari_algorithm import calculate_ari

    result = calculate_ari(temperature=32.0, humidity=80.0, moisture_pct=14.8, duration_hours=4.0)
    # Returns: {"ari_score": 70.0+, "risk_level": "High", "factors": {...}}
"""

import math
from typing import TypedDict


class ARIFactors(TypedDict):
    temperature_factor: float
    humidity_factor: float
    moisture_factor: float
    duration_factor: float


class ARIResult(TypedDict):
    ari_score: float
    risk_level: str
    risk_color: str
    recommended_action: str
    moisture_override: bool   # True when the high-MC safety floor was applied
    factors: ARIFactors


# ─── Weight Constants ────────────────────────────────────────────────────────
# Revised to incorporate Moisture Content (MC) as an independent risk factor.
# FAO / East African grain storage standards inform the MC thresholds.
WEIGHT_TEMPERATURE = 0.25
WEIGHT_HUMIDITY    = 0.30
WEIGHT_MOISTURE    = 0.30
WEIGHT_DURATION    = 0.15

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

# ─── Moisture Content (MC) Model ─────────────────────────────────────────────
# Based on FAO (2011) and MAAIF Uganda grain storage guidelines:
#   - Safe storage MC for maize/sorghum: ≤ 13.5%
#   - Elevated risk zone: 13.5% – 15.0% (linear ramp)
#   - Critical / maximum risk: ≥ 15.0%
# Safety override: MC ≥ 14.5% unconditionally floors ARI at High-Risk (≥ 70.0)
MOIST_SAFE_PCT      = 13.5   # % — below this, F(M) = 0 (safe)
MOIST_CRITICAL_PCT  = 15.0   # % — at or above this, F(M) = 1 (max risk)
MOIST_OVERRIDE_PCT  = 14.5   # % — safety floor: forces ARI ≥ 70.0
MOIST_OVERRIDE_FLOOR = 70.0  # Minimum ARI when override is applied

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


def _moisture_factor(moisture_pct: float | None) -> float:
    """
    Linear moisture content factor based on FAO / East African grain standards.

    F(M) = 0.0           if moisture_pct is None or <= MOIST_SAFE_PCT (13.5%)
    F(M) = linear ramp   if MOIST_SAFE_PCT < moisture_pct < MOIST_CRITICAL_PCT
    F(M) = 1.0           if moisture_pct >= MOIST_CRITICAL_PCT (15.0%)
    """
    if moisture_pct is None or moisture_pct <= MOIST_SAFE_PCT:
        return 0.0
    if moisture_pct >= MOIST_CRITICAL_PCT:
        return 1.0
    return (moisture_pct - MOIST_SAFE_PCT) / (MOIST_CRITICAL_PCT - MOIST_SAFE_PCT)


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
    moisture_pct: float | None = None,
    duration_hours: float = 0.0,
) -> ARIResult:
    """
    Calculate Aflatoxin Risk Index for given environmental conditions.

    Implements a 4-factor weighted model (T, H, M, D):
      ARI = 100 × (0.25×F(T) + 0.30×F(H) + 0.30×F(M) + 0.15×F(D)/F(D)_max)

    Safety Override:
      If moisture_pct >= 14.5% (MOIST_OVERRIDE_PCT), the raw ARI score is
      unconditionally raised to at least 70.0 (High Risk floor), regardless
      of temperature or humidity readings.

    Args:
        temperature:    Temperature in °C (from DHT22)
        humidity:       Relative humidity percentage (from DHT22)
        moisture_pct:   Grain/soil moisture % from capacitive sensor (optional).
                        Defaults to None (moisture factor is ignored).
        duration_hours: Continuous hours under high-risk conditions (default 0)

    Returns:
        ARIResult dict with ari_score (0–100), risk_level, risk_color,
        recommended_action, moisture_override flag, and individual factor breakdown.

    Examples:
        >>> calculate_ari(30.0, 85.0, 14.8, 8.0)['risk_level']
        'High'
        >>> calculate_ari(15.0, 55.0, 12.0, 0.0)['risk_level']
        'Low'
        >>> calculate_ari(28.0, 74.0, None, 3.0)['risk_level']
        'Medium'
        >>> calculate_ari(15.0, 55.0, 14.6, 0.0)['risk_level']  # moisture override
        'High'
    """
    f_t = _temperature_factor(temperature)
    f_h = _humidity_factor(humidity)
    f_m = _moisture_factor(moisture_pct)
    f_d = _duration_factor(duration_hours)

    raw_score = (
        WEIGHT_TEMPERATURE * f_t
        + WEIGHT_HUMIDITY   * f_h
        + WEIGHT_MOISTURE   * f_m
        + WEIGHT_DURATION   * (f_d / DUR_MAX_FACTOR)
    )
    ari_score = round(min(100.0, max(0.0, raw_score * 100.0)), 2)

    # ── Safety Override: high MC unconditionally triggers High Risk ──────────
    moisture_override = (
        moisture_pct is not None
        and moisture_pct >= MOIST_OVERRIDE_PCT
        and ari_score < MOIST_OVERRIDE_FLOOR
    )
    if moisture_override:
        ari_score = MOIST_OVERRIDE_FLOOR

    risk_level, risk_color, recommended_action = _classify_risk(ari_score)

    return ARIResult(
        ari_score=ari_score,
        risk_level=risk_level,
        risk_color=risk_color,
        recommended_action=recommended_action,
        moisture_override=moisture_override,
        factors=ARIFactors(
            temperature_factor=round(f_t, 4),
            humidity_factor=round(f_h, 4),
            moisture_factor=round(f_m, 4),
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
    # (temp, humidity, moisture_pct, duration, expected_risk)
    (10.0,  65.0, None,  0.0, 'Low'),     # At minimum viable growth boundary
    (30.0,  85.0, 14.8,  8.0, 'High'),    # Optimal conditions + unsafe moisture
    (25.0,  74.0, 12.0,  3.0, 'Medium'),  # Mild risk zone, safe moisture
    (15.0,  55.0, None,  0.0, 'Low'),     # Safe cold dry storage
    (35.0,  90.0, 16.0, 12.0, 'High'),    # Extreme risk + critical moisture
    (20.0,  70.0, 13.0,  6.0, 'Low'),     # Moderate conditions, safe moisture
    (15.0,  50.0, 14.6,  0.0, 'High'),    # Cold + dry, but moisture override fires
]
