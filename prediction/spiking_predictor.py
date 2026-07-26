"""Spike-based anomaly detector -- runs the REAL Spikeling neuromorphic
runtime (github.com/gbranaa4-hue/Spikeling), the same DSL/engine that
drives NPC brains in the `tribe` game and a live Arduino sensor grid,
not a one-off reimplementation of LIF neurons for this project alone.

Genuinely different mechanism than trend_predictor.py's linear
regression: each parameter drives its own LIF neuron with a "stress
current" (see pond_brain.spk). Zero current at an ideal reading, so it
leaks straight back to rest and a single noisy reading can't trip it;
a neuron only fires once enough current has integrated -- instantly
under a critical reading, or after several consecutive stressed
readings accumulate past threshold. It doesn't predict the future the
way the trend predictor does (no "crosses in N hours"); it answers a
different question -- "has this been a real, sustained problem, or
noise?" -- which main.py runs alongside the trend predictor, not
instead of it, logging each to its own `detector` column so Grafana
can show whether they agree.

Requires the Spikeling repo cloned as a sibling directory next to this
pond-health checkout (..\\Spikeling), or SPIKELING_CORE_PATH pointing at
its core/ folder. If neither is found, the constructor raises
SpikelingNotFound -- main.py catches that and just skips the spiking
detector, since the trend predictor works fine on its own.
"""
import os
import sys
import tempfile
from collections import deque
from typing import Deque, Dict, List, Tuple

from prediction.thresholds import THRESHOLDS, Range
from prediction.trend_predictor import PARAM_FIELDS, PARAM_LABELS, Prediction
from sensors.sensor_interface import Reading

_SPK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pond_brain.spk")

# Must match the neuron names in pond_brain.spk exactly.
NEURON_NAMES = {
    "dissolved_oxygen_mg_l": "DissolvedOxygen",
    "ph": "PH",
    "temperature_c": "Temperature",
    "turbidity_ntu": "Turbidity",
    "conductivity_us_cm": "Conductivity",
}

# Drive current per reading, based on which zone (from thresholds.py)
# the value is in. Mirrors trend_predictor._classify()'s cutoffs
# exactly (critical_low/stress_low/stress_high/critical_high --
# ideal_low/high are unused there too, for the same reason: _classify
# never reads them).
DRIVE_IDEAL = 0.0
DRIVE_STRESS = 20.0     # ~8 sustained-stress readings to fire (leak=8, threshold=100)
DRIVE_CRITICAL = 110.0  # fires on this reading alone

# How far back (sim seconds) a fired spike still counts toward "this is
# an active alarm" -- old spikes age out so a single past incident
# doesn't alarm forever.
ALERT_WINDOW_S = 4 * 3600.0

_DRIVE_FOR_ZONE = {"ideal": DRIVE_IDEAL, "stress": DRIVE_STRESS, "critical": DRIVE_CRITICAL}


class SpikelingNotFound(RuntimeError):
    pass


def _locate_spikeling_core() -> str:
    env_path = os.environ.get("SPIKELING_CORE_PATH")
    if env_path and os.path.isdir(env_path):
        return env_path
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sibling = os.path.abspath(os.path.join(repo_root, "..", "Spikeling", "core"))
    if os.path.isdir(sibling):
        return sibling
    raise SpikelingNotFound(
        "Couldn't find the Spikeling engine. Clone "
        "https://github.com/gbranaa4-hue/Spikeling next to this pond-health "
        "checkout, or set SPIKELING_CORE_PATH to its core/ folder."
    )


def _classify_zone(value: float, rng: Range) -> str:
    """Same zones as trend_predictor._classify() -- reimplemented
    (not imported) so this module's only real dependency on
    thresholds.py is the Range values themselves."""
    if rng.critical_low is not None and value <= rng.critical_low:
        return "critical"
    if rng.critical_high is not None and value >= rng.critical_high:
        return "critical"
    if rng.stress_low is not None and value <= rng.stress_low:
        return "stress"
    if rng.stress_high is not None and value >= rng.stress_high:
        return "stress"
    return "ideal"


class SpikingAnomalyDetector:
    def __init__(self):
        core_path = _locate_spikeling_core()
        if core_path not in sys.path:
            sys.path.insert(0, core_path)
        from compiler.compiler import compile_file
        from runtime.runtime import SpikelingRuntime

        build_dir = tempfile.mkdtemp(prefix="pond_spikeling_")
        ast = compile_file(_SPK_PATH, output_dir=build_dir)
        self._runtime = SpikelingRuntime(ast)
        self._spike_history: Dict[str, Deque[float]] = {p: deque() for p in PARAM_FIELDS}
        self._latest: Dict[str, Tuple[float, str]] = {}

    def ingest(self, reading: Reading) -> None:
        t_ms = reading.timestamp * 1000.0
        values = {
            "dissolved_oxygen_mg_l": reading.dissolved_oxygen_mg_l,
            "ph": reading.ph,
            "temperature_c": reading.temperature_c,
            "turbidity_ntu": reading.turbidity_ntu,
            "conductivity_us_cm": reading.conductivity_us_cm,
        }
        for param, value in values.items():
            zone = _classify_zone(value, THRESHOLDS[param])
            self._latest[param] = (value, zone)
            fired = self._runtime.stimulate(
                NEURON_NAMES[param], t_ms, drive=_DRIVE_FOR_ZONE[zone]
            ) is not None

            history = self._spike_history[param]
            if fired:
                history.append(reading.timestamp)
            while history and reading.timestamp - history[0] > ALERT_WINDOW_S:
                history.popleft()

    def predict_all(self) -> List[Prediction]:
        window_h = ALERT_WINDOW_S / 3600.0
        predictions = []
        for param in PARAM_FIELDS:
            if param not in self._latest:
                continue
            value, zone = self._latest[param]
            recent_spikes = len(self._spike_history[param])
            label = PARAM_LABELS[param]

            if recent_spikes == 0:
                status = "ideal"
                explanation = f"{label}'s neuron hasn't fired in the last {window_h:.0f}h."
            elif zone == "critical":
                status = "critical"
                explanation = (
                    f"{label}'s neuron fired {recent_spikes}x in the last {window_h:.0f}h "
                    f"(currently critical -- firing on every reading)."
                )
            else:
                status = "stress"
                explanation = (
                    f"{label}'s neuron fired {recent_spikes}x in the last {window_h:.0f}h -- "
                    f"sustained stress has integrated enough charge to alarm."
                )

            predictions.append(Prediction(
                parameter=param,
                current_value=value,
                trend_per_hour=0.0,
                status=status,
                crossing_threshold=None,
                hours_to_threshold=None,
                explanation=explanation,
            ))
        return predictions
