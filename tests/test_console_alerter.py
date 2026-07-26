from alerts.console_alerter import ConsoleAlerter
from prediction.trend_predictor import Prediction


def test_forecast_icon_used_when_ideal_but_crossing_predicted(capsys):
    pred = Prediction(
        parameter="dissolved_oxygen_mg_l", current_value=4.65, trend_per_hour=-0.4,
        status="ideal", crossing_threshold="stress_low", hours_to_threshold=1.5,
        explanation="Dissolved oxygen is falling and will cross stress low in 1.5 hours.",
    )
    ConsoleAlerter().notify(pred, ["Turn on aeration."])
    out = capsys.readouterr().out
    assert out.startswith("[FORECAST]")


def test_critical_icon_used_when_already_critical(capsys):
    pred = Prediction(
        parameter="dissolved_oxygen_mg_l", current_value=1.5, trend_per_hour=-0.4,
        status="critical", explanation="Dissolved oxygen is critically low.",
    )
    ConsoleAlerter().notify(pred, ["Run aeration now."])
    out = capsys.readouterr().out
    assert out.startswith("[CRITICAL]")
