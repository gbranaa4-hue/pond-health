import pytest

from prediction.spiking_predictor import SpikelingNotFound, SpikingAnomalyDetector
from sensors.sensor_interface import Reading

try:
    SpikingAnomalyDetector()
    _SPIKELING_AVAILABLE = True
except SpikelingNotFound:
    _SPIKELING_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _SPIKELING_AVAILABLE,
    reason="Spikeling engine not found -- clone github.com/gbranaa4-hue/Spikeling "
           "as a sibling directory, or set SPIKELING_CORE_PATH, to run these.",
)


def _reading(t, **overrides):
    base = dict(
        timestamp=t, temperature_c=22.0, ph=7.2, turbidity_ntu=5.0,
        dissolved_oxygen_mg_l=7.0, conductivity_us_cm=300.0,
    )
    base.update(overrides)
    return Reading(**base)


def test_stays_ideal_under_healthy_readings():
    detector = SpikingAnomalyDetector()
    for i in range(20):
        detector.ingest(_reading(t=i * 900.0))
    statuses = {p.parameter: p.status for p in detector.predict_all()}
    assert all(s == "ideal" for s in statuses.values())


def test_critical_reading_fires_immediately():
    detector = SpikingAnomalyDetector()
    detector.ingest(_reading(t=0.0, dissolved_oxygen_mg_l=1.0))  # below critical_low=2.0
    statuses = {p.parameter: p.status for p in detector.predict_all()}
    assert statuses["dissolved_oxygen_mg_l"] == "critical"


def test_single_noisy_stress_reading_does_not_fire():
    # One borderline reading shouldn't be enough to alarm -- that's the
    # whole point of requiring integrated charge over several readings.
    detector = SpikingAnomalyDetector()
    detector.ingest(_reading(t=0.0, dissolved_oxygen_mg_l=3.5))  # below stress_low=4.0
    statuses = {p.parameter: p.status for p in detector.predict_all()}
    assert statuses["dissolved_oxygen_mg_l"] == "ideal"


def test_sustained_stress_eventually_fires():
    detector = SpikingAnomalyDetector()
    for i in range(12):
        detector.ingest(_reading(t=i * 900.0, dissolved_oxygen_mg_l=3.5))
    statuses = {p.parameter: p.status for p in detector.predict_all()}
    assert statuses["dissolved_oxygen_mg_l"] in ("stress", "critical")
