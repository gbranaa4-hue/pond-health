from grafana.generate_dashboard import build_threshold_steps
from prediction.thresholds import THRESHOLDS


def test_dissolved_oxygen_steps_low_side_only():
    steps = build_threshold_steps(THRESHOLDS["dissolved_oxygen_mg_l"])
    assert steps == [
        {"value": None, "color": "red"},
        {"value": 2.0, "color": "orange"},
        {"value": 4.0, "color": "green"},
    ]


def test_ph_steps_both_sides():
    steps = build_threshold_steps(THRESHOLDS["ph"])
    assert steps == [
        {"value": None, "color": "red"},
        {"value": 5.5, "color": "orange"},
        {"value": 6.5, "color": "green"},
        {"value": 9.0, "color": "orange"},
        {"value": 9.5, "color": "red"},
    ]


def test_turbidity_steps_high_side_only_no_critical_low_tier():
    # No critical_low/stress_low at all -- base zone should be green,
    # not red, since _classify() never flags this parameter as a low-end
    # problem.
    steps = build_threshold_steps(THRESHOLDS["turbidity_ntu"])
    assert steps == [
        {"value": None, "color": "green"},
        {"value": 50.0, "color": "orange"},
        {"value": 100.0, "color": "red"},
    ]


def test_temperature_steps_stress_low_without_critical_low():
    # Has a stress_low but no critical_low -- base color should be
    # orange (stress), not red (critical), matching _classify()'s
    # behavior of never returning "critical" when critical_low is None.
    steps = build_threshold_steps(THRESHOLDS["temperature_c"])
    assert steps[0] == {"value": None, "color": "orange"}
