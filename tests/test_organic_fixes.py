from diagnosis.organic_fixes import recommend
from prediction.trend_predictor import Prediction


def test_no_fixes_when_ideal():
    pred = Prediction(parameter="ph", current_value=7.5, trend_per_hour=0.0, status="ideal")
    assert recommend(pred) == []


def test_fixes_present_for_critical_oxygen():
    pred = Prediction(parameter="dissolved_oxygen_mg_l", current_value=1.5,
                       trend_per_hour=-0.5, status="critical")
    fixes = recommend(pred)
    assert len(fixes) > 0
    assert any("aeration" in f.lower() for f in fixes)


def test_unknown_parameter_returns_empty():
    pred = Prediction(parameter="nonexistent", current_value=1.0,
                       trend_per_hour=0.0, status="critical")
    assert recommend(pred) == []
