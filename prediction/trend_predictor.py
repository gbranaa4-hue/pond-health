"""
Transparent, explainable trend-based prediction -- not a black-box ML
model. No real historical pond data exists yet to train one honestly, so
v1 reasons the way an experienced pond keeper would: look at the recent
trend for each parameter, extrapolate it forward, and say plainly "at
this rate, X crosses the danger line in Y hours, because Z."

Once real sensor history is being logged, swap `_linear_trend()` below
for a trained model (e.g. scikit-learn RandomForestRegressor, or an
LSTM) without touching the diagnosis/alert layers -- they only depend on
the Prediction shape returned here.
"""
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Tuple
from collections import deque

from prediction.thresholds import THRESHOLDS, Range
from sensors.sensor_interface import Reading

PARAM_FIELDS = [
    "dissolved_oxygen_mg_l", "ph", "temperature_c",
    "turbidity_ntu", "conductivity_us_cm",
]

PARAM_LABELS = {
    "dissolved_oxygen_mg_l": "Dissolved oxygen",
    "ph": "pH",
    "temperature_c": "Temperature",
    "turbidity_ntu": "Turbidity",
    "conductivity_us_cm": "Conductivity",
}

# Don't warn about a crossing more than this many hours out.
MAX_WARNING_HORIZON_HOURS = 72.0


@dataclass
class Prediction:
    parameter: str
    current_value: float
    trend_per_hour: float
    status: str                              # "ideal" | "stress" | "critical"
    crossing_threshold: Optional[str] = None  # e.g. "stress_low"
    hours_to_threshold: Optional[float] = None
    explanation: str = ""


class TrendPredictor:
    def __init__(self, history_len: int = 48):
        self._history: Dict[str, Deque[Tuple[float, float]]] = {
            p: deque(maxlen=history_len) for p in PARAM_FIELDS
        }

    def ingest(self, reading: Reading) -> None:
        t = reading.timestamp
        self._history["dissolved_oxygen_mg_l"].append((t, reading.dissolved_oxygen_mg_l))
        self._history["ph"].append((t, reading.ph))
        self._history["temperature_c"].append((t, reading.temperature_c))
        self._history["turbidity_ntu"].append((t, reading.turbidity_ntu))
        self._history["conductivity_us_cm"].append((t, reading.conductivity_us_cm))

    def predict_all(self) -> List[Prediction]:
        return [self._predict_one(p) for p in PARAM_FIELDS if len(self._history[p]) >= 2]

    def _predict_one(self, param: str) -> Prediction:
        points = list(self._history[param])
        slope_per_s, current_value = _linear_trend(points)
        slope_per_hr = slope_per_s * 3600.0
        rng: Range = THRESHOLDS[param]

        status = _classify(current_value, rng)
        crossing, hours = _project_crossing(current_value, slope_per_hr, rng)

        label = PARAM_LABELS[param]
        if crossing and hours is not None:
            direction = "rising" if slope_per_hr > 0 else "falling"
            explanation = (
                f"{label} is {direction} at {abs(slope_per_hr):.2f}/hr and will cross "
                f"the {crossing.replace('_', ' ')} threshold in about {hours:.1f} hours "
                f"if this continues."
            )
        elif status != "ideal":
            explanation = f"{label} is currently outside the ideal range ({current_value})."
        else:
            explanation = f"{label} is stable and within the ideal range."

        return Prediction(
            parameter=param,
            current_value=current_value,
            trend_per_hour=slope_per_hr,
            status=status,
            crossing_threshold=crossing,
            hours_to_threshold=hours,
            explanation=explanation,
        )


def _linear_trend(points: List[Tuple[float, float]]) -> Tuple[float, float]:
    """Least-squares slope (value per second) + latest value."""
    n = len(points)
    if n < 2:
        return 0.0, points[-1][1]
    t0 = points[0][0]
    xs = [p[0] - t0 for p in points]
    ys = [p[1] for p in points]
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    den = sum((x - mean_x) ** 2 for x in xs)
    slope = num / den if den > 1e-9 else 0.0
    return slope, ys[-1]


def _classify(value: float, rng: Range) -> str:
    if rng.critical_low is not None and value <= rng.critical_low:
        return "critical"
    if rng.critical_high is not None and value >= rng.critical_high:
        return "critical"
    if rng.stress_low is not None and value <= rng.stress_low:
        return "stress"
    if rng.stress_high is not None and value >= rng.stress_high:
        return "stress"
    return "ideal"


def _project_crossing(
    value: float, slope_per_hr: float, rng: Range
) -> Tuple[Optional[str], Optional[float]]:
    """
    If the current trend continues, which threshold gets crossed next and
    in how many hours? Returns (None, None) if the trend points away from
    danger, is essentially flat, or the crossing is too far out to be
    worth warning about yet.
    """
    if abs(slope_per_hr) < 1e-6:
        return None, None

    candidates: List[Tuple[str, float]] = []
    if slope_per_hr < 0:
        for name in ("stress_low", "critical_low"):
            bound = getattr(rng, name)
            if bound is not None and value > bound:
                candidates.append((name, (value - bound) / (-slope_per_hr)))
    else:
        for name in ("stress_high", "critical_high"):
            bound = getattr(rng, name)
            if bound is not None and value < bound:
                candidates.append((name, (bound - value) / slope_per_hr))

    if not candidates:
        return None, None
    candidates.sort(key=lambda c: c[1])
    name, hours = candidates[0]
    if hours > MAX_WARNING_HORIZON_HOURS:
        return None, None
    return name, hours
