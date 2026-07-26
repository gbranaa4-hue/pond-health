"""
Maps a Prediction's (parameter, status) to concrete organic/low-tech
fixes -- the "prescription" layer. These recommendations are standard
aquaculture/pond-keeping practice, not novel; the value this project
adds is surfacing the right one automatically, before the problem is
visible to the naked eye.
"""
from typing import List

from prediction.trend_predictor import Prediction

FIXES = {
    "dissolved_oxygen_mg_l": {
        "critical": [
            "Run/add aeration right now (air stone, fountain, or waterfall pump).",
            "Do a partial water change with aerated water if aeration alone won't act fast enough.",
            "Stop feeding until oxygen recovers -- digestion consumes additional oxygen.",
        ],
        "stress": [
            "Turn on supplemental aeration, especially overnight (respiration drops DO until dawn).",
            "Add oxygenating plants (anacharis, hornwort) to boost daytime photosynthesis.",
            "Reduce stocking density or feeding rate if this recurs.",
        ],
    },
    "ph": {
        "critical": [
            "If too low (acidic): add crushed coral or agricultural limestone to buffer upward slowly.",
            "If too high (alkaline): add peat moss, or do a partial water change with neutral source water.",
            "Change pH gradually -- more than about 0.3/day stresses fish even toward a 'correct' target.",
        ],
        "stress": [
            "Monitor daily; a slow organic buffer (crushed coral for low pH) is safer than a fast chemical fix.",
        ],
    },
    "temperature_c": {
        "critical": [
            "Add shade (floating plants, shade cloth) to cut peak daytime heating.",
            "Increase aeration/circulation -- warm water holds less oxygen, so counter it directly.",
        ],
        "stress": [
            "Add partial shade cover for the hottest part of the day.",
        ],
    },
    "turbidity_ntu": {
        "critical": [
            "Add a natural flocculant (barley straw extract or gypsum) to help particles settle.",
            "Check for and stop any active runoff/erosion source into the pond.",
            "Improve biofiltration with a planted gravel/reed bed if this is a recurring pattern.",
        ],
        "stress": [
            "Add floating plants or a simple planted bio-filter to naturally polish water clarity.",
        ],
    },
    "conductivity_us_cm": {
        "critical": [
            "Investigate a possible contamination/runoff source (road salt, fertilizer, greywater).",
            "Dilute with a partial water change using known low-conductivity source water.",
        ],
        "stress": [
            "Keep monitoring -- conductivity swings often precede a nutrient or pollution issue.",
        ],
    },
}


def recommend(prediction: Prediction) -> List[str]:
    """Organic fixes for the current status ("ideal" -> no fixes needed)."""
    if prediction.status == "ideal":
        return []
    return FIXES.get(prediction.parameter, {}).get(prediction.status, [])
