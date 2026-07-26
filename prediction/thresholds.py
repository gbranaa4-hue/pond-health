"""
Well-established aquaculture/pond-keeping thresholds -- the "vital sign"
boundaries the prediction and diagnosis layers reason about. Values are
commonly-cited ranges for warm-water pond fish (koi/goldfish/bass);
adjust for your specific stock.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Range:
    critical_low: Optional[float] = None
    stress_low: Optional[float] = None
    ideal_low: Optional[float] = None
    ideal_high: Optional[float] = None
    stress_high: Optional[float] = None
    critical_high: Optional[float] = None


THRESHOLDS = {
    "dissolved_oxygen_mg_l": Range(
        critical_low=2.0, stress_low=4.0, ideal_low=5.0, ideal_high=12.0,
    ),
    "ph": Range(
        critical_low=5.5, stress_low=6.5, ideal_low=6.8, ideal_high=8.5,
        stress_high=9.0, critical_high=9.5,
    ),
    "temperature_c": Range(
        stress_low=10.0, ideal_low=15.0, ideal_high=28.0,
        stress_high=32.0, critical_high=35.0,
    ),
    "turbidity_ntu": Range(
        ideal_low=0.0, ideal_high=25.0, stress_high=50.0, critical_high=100.0,
    ),
    "conductivity_us_cm": Range(
        ideal_low=150.0, ideal_high=800.0, stress_high=1500.0, critical_high=3000.0,
    ),
}
