"""
Simulated pond sensor data.

No physical sensors exist yet -- this generates plausible, physically
grounded readings (real diurnal DO/temperature cycles, realistic noise)
so the prediction/diagnosis/alert pipeline can be built and tested now.
Supports injectable "scenarios" (e.g. a developing algae bloom, an
overnight oxygen crash) so the prediction layer can be verified against
a known, scheduled problem before ever touching real hardware.

Replace this file with a real hardware reader later (e.g. one that polls
an ESP32 over serial, or reads I2C probes on a Raspberry Pi); nothing
else in the project needs to change as long as it returns the same
Reading shape.
"""
import math
import random

from sensors.sensor_interface import Reading, SensorReader


class Scenario:
    """A named perturbation applied on top of the baseline simulation."""
    NORMAL = "normal"
    ALGAE_BLOOM_DEVELOPING = "algae_bloom_developing"
    NIGHT_OXYGEN_CRASH = "night_oxygen_crash"
    AMMONIA_BUILDUP = "ammonia_buildup"
    RUNOFF_TURBIDITY_SPIKE = "runoff_turbidity_spike"


def do_saturation_mg_l(temp_c: float) -> float:
    """
    Approximate dissolved-oxygen SATURATION ceiling (mg/L) at 1 atm as a
    function of water temperature -- warmer water measurably holds less
    oxygen. Simplified empirical fit (APHA/USGS-style approximation),
    accurate to within ~0.2 mg/L of standard tables in the pond-relevant
    15-30C range. Good enough for a heuristic predictor; not a substitute
    for a lab-grade Benson-Krause table.
    """
    return 14.62 - 0.3898 * temp_c + 0.006969 * temp_c ** 2 - 0.0000594 * temp_c ** 3


class SimulatedPondReader(SensorReader):
    """
    Baseline model:
      - Water temperature follows a diurnal sine wave (coolest ~5am,
        warmest ~3pm) plus sensor noise.
      - Dissolved oxygen follows the real photosynthesis day/night cycle
        (algae/plants add O2 during daylight, consume it all night --
        the classic pre-dawn DO crash) layered on top of the
        temperature-linked saturation ceiling.
      - pH, turbidity, and conductivity drift slowly around realistic
        pond baselines via a bounded random walk.

    A scenario, once started, ramps a specific parameter toward a bad
    state over `duration_s` so the prediction layer has a genuine trend
    to detect, not just noise.
    """

    def __init__(self, start_time: float = 0.0, seed: int = 42):
        self._t0 = start_time
        self._rng = random.Random(seed)
        self._scenario = Scenario.NORMAL
        self._scenario_start = 0.0
        self._scenario_duration = 1.0
        self._ph_walk = 7.6
        self._turbidity_walk = 8.0
        self._conductivity_walk = 420.0

    def start_scenario(self, scenario: str, duration_s: float, at_time: float = 0.0) -> None:
        """Begin ramping toward a bad condition over duration_s seconds."""
        self._scenario = scenario
        self._scenario_start = at_time
        self._scenario_duration = max(duration_s, 1.0)

    def clear_scenario(self) -> None:
        self._scenario = Scenario.NORMAL

    def _scenario_progress(self, now: float) -> float:
        if self._scenario == Scenario.NORMAL:
            return 0.0
        elapsed = now - self._scenario_start
        return max(0.0, min(1.0, elapsed / self._scenario_duration))

    def read(self, at_time: float = None) -> Reading:
        now = at_time if at_time is not None else self._t0
        elapsed_h = (now - self._t0) / 3600.0
        hour_of_day = elapsed_h % 24.0

        diurnal = math.sin((hour_of_day - 9.0) / 24.0 * 2 * math.pi)
        temp = 22.0 + diurnal * 4.0 + self._rng.gauss(0, 0.15)

        do_cycle = math.sin((hour_of_day - 15.0) / 24.0 * 2 * math.pi)
        do_ceiling = do_saturation_mg_l(temp)
        do = do_ceiling * (0.72 + 0.18 * do_cycle) + self._rng.gauss(0, 0.08)

        self._ph_walk += self._rng.gauss(0, 0.01)
        self._ph_walk = max(6.0, min(9.5, self._ph_walk))
        self._turbidity_walk += self._rng.gauss(0, 0.15)
        self._turbidity_walk = max(1.0, self._turbidity_walk)
        self._conductivity_walk += self._rng.gauss(0, 2.0)

        ph = self._ph_walk
        turbidity = self._turbidity_walk
        conductivity = self._conductivity_walk

        progress = self._scenario_progress(now)
        if self._scenario == Scenario.ALGAE_BLOOM_DEVELOPING:
            turbidity += progress * 35.0
            do += progress * 3.0
            ph += progress * 0.6
        elif self._scenario == Scenario.NIGHT_OXYGEN_CRASH:
            do -= progress * (do - 1.5)
        elif self._scenario == Scenario.AMMONIA_BUILDUP:
            ph -= progress * 1.0
            turbidity += progress * 8.0
        elif self._scenario == Scenario.RUNOFF_TURBIDITY_SPIKE:
            turbidity += progress * 60.0
            conductivity += progress * 150.0

        return Reading(
            timestamp=now,
            temperature_c=round(temp, 2),
            ph=round(max(0.0, min(14.0, ph)), 2),
            turbidity_ntu=round(max(0.0, turbidity), 2),
            dissolved_oxygen_mg_l=round(max(0.0, do), 2),
            conductivity_us_cm=round(max(0.0, conductivity), 1),
        )
