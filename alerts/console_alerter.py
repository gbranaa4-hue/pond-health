"""
Simplest possible alert channel: readable console output. Add an email,
SMS (e.g. Twilio), or smart-home webhook alerter later by implementing
the same `notify(prediction, fixes)` shape.
"""
from typing import List

from prediction.trend_predictor import Prediction

_ICONS = {"ideal": "OK", "stress": "WARNING", "critical": "CRITICAL"}


class ConsoleAlerter:
    def notify(self, prediction: Prediction, fixes: List[str]) -> None:
        # A prediction can flag a crossing while still technically "ideal"
        # right now -- that's a forecast, not an all-clear, so it needs its
        # own label instead of reusing "OK".
        if prediction.status == "ideal" and prediction.crossing_threshold is not None:
            icon = "FORECAST"
        else:
            icon = _ICONS[prediction.status]
        print(f"[{icon}] {prediction.explanation}")
        for fix in fixes:
            print(f"    -> {fix}")
