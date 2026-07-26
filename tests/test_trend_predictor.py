from prediction.trend_predictor import TrendPredictor, _linear_trend, _classify, _project_crossing
from prediction.thresholds import THRESHOLDS
from sensors.sensor_interface import Reading


def test_linear_trend_detects_falling_slope():
    points = [(0, 10.0), (3600, 8.0), (7200, 6.0)]
    slope, latest = _linear_trend(points)
    assert latest == 6.0
    assert slope < 0


def test_linear_trend_single_point_has_no_slope():
    slope, latest = _linear_trend([(0, 5.0)])
    assert slope == 0.0
    assert latest == 5.0


def test_classify_thresholds():
    rng = THRESHOLDS["dissolved_oxygen_mg_l"]
    assert _classify(1.0, rng) == "critical"
    assert _classify(3.0, rng) == "stress"
    assert _classify(7.0, rng) == "ideal"


def test_project_crossing_predicts_hours_ahead():
    rng = THRESHOLDS["dissolved_oxygen_mg_l"]
    # Falling 1.0 mg/L per hour from 6.0 -- stress_low=4.0 is 2 hours away.
    name, hours = _project_crossing(6.0, -1.0, rng)
    assert name == "stress_low"
    assert abs(hours - 2.0) < 0.01


def test_project_crossing_ignores_safe_direction():
    rng = THRESHOLDS["dissolved_oxygen_mg_l"]
    name, hours = _project_crossing(6.0, 1.0, rng)
    assert name is None


def test_project_crossing_ignores_far_horizon():
    rng = THRESHOLDS["dissolved_oxygen_mg_l"]
    # Falling so slowly that stress_low is nearly a week away.
    name, hours = _project_crossing(6.0, -0.01, rng)
    assert name is None


def test_ingest_and_predict_all_flags_falling_oxygen():
    predictor = TrendPredictor()
    t = 0.0
    do = 8.0
    for _ in range(6):
        reading = Reading(
            timestamp=t, temperature_c=24.0, ph=7.5,
            turbidity_ntu=10.0, dissolved_oxygen_mg_l=do,
            conductivity_us_cm=400.0,
        )
        predictor.ingest(reading)
        t += 3600
        do -= 0.8
    predictions = {p.parameter: p for p in predictor.predict_all()}
    do_pred = predictions["dissolved_oxygen_mg_l"]
    assert do_pred.trend_per_hour < 0
    assert do_pred.crossing_threshold is not None
