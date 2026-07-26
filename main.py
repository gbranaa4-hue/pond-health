"""
Pond health monitor -- entry point.

Runs the simulated sensor -> trend prediction -> organic-fix diagnosis
-> console alert pipeline. No real hardware needed yet; see
sensors/simulated_reader.py for the simulation model and
sensors/sensor_interface.py for the interface a real hardware reader
would implement to drop in later.

Usage:
    python main.py                                    # normal 48h day/night cycle
    python main.py --scenario night_oxygen_crash
    python main.py --scenario algae_bloom_developing --hours 72
"""
import argparse
import dataclasses
import time
from typing import Optional

from sensors.simulated_reader import SimulatedPondReader, Scenario
from prediction.trend_predictor import TrendPredictor
from prediction.spiking_predictor import SpikingAnomalyDetector, SpikelingNotFound
from diagnosis.organic_fixes import recommend
from alerts.console_alerter import ConsoleAlerter
from storage.pond_store import PondHistoryStore

SCENARIOS = {
    "algae_bloom_developing": Scenario.ALGAE_BLOOM_DEVELOPING,
    "night_oxygen_crash": Scenario.NIGHT_OXYGEN_CRASH,
    "ammonia_buildup": Scenario.AMMONIA_BUILDUP,
    "runoff_turbidity_spike": Scenario.RUNOFF_TURBIDITY_SPIKE,
}


def run(hours: float, step_minutes: float, scenario: str = None,
        scenario_start_hour: float = 6.0, scenario_duration_hours: float = 12.0,
        db_path: Optional[str] = "pond_health.db", use_spiking: bool = True) -> None:
    reader = SimulatedPondReader(start_time=0.0)
    predictor = TrendPredictor()
    alerter = ConsoleAlerter()
    store = PondHistoryStore(db_path) if db_path else None

    spiking = None
    if use_spiking:
        try:
            spiking = SpikingAnomalyDetector()
        except SpikelingNotFound as e:
            print(f"[pond-health] Spiking detector unavailable, continuing with trend-only: {e}")

    if scenario:
        reader.start_scenario(
            SCENARIOS[scenario],
            duration_s=scenario_duration_hours * 3600,
            at_time=scenario_start_hour * 3600,
        )

    step_s = step_minutes * 60
    total_steps = int(hours * 3600 / step_s)
    total_duration_s = hours * 3600

    # The simulation fast-forwards through `hours` of pond time in a
    # tight loop, so `reading.timestamp` (simulated seconds-from-start)
    # is meaningless as a calendar date -- anchor it so the LAST reading
    # lands at real "now" and earlier ones fall into the real past. That
    # way a dashboard opened right after a run, with its default "last
    # 24h"-style relative time range, immediately shows the run's data
    # without the viewer having to hand-pick a custom time range.
    wall_now = time.time()

    for i in range(total_steps):
        sim_t = i * step_s
        reading = reader.read(at_time=sim_t)
        predictor.ingest(reading)
        if spiking:
            spiking.ingest(reading)
        real_t = wall_now - (total_duration_s - sim_t)

        if store:
            store.log_reading(real_t, reading)

        hh = int((sim_t / 3600) % 24)
        print(f"\n--- t={sim_t / 3600:.1f}h (hour {hh:02d}:00) ---")
        print(
            f"  temp={reading.temperature_c}C  pH={reading.ph}  "
            f"turbidity={reading.turbidity_ntu}NTU  DO={reading.dissolved_oxygen_mg_l}mg/L  "
            f"EC={reading.conductivity_us_cm}uS/cm"
        )

        for pred in predictor.predict_all():
            # Alert if it's already a problem, OR if the trend says it's
            # headed for one -- the whole point of prediction is warning
            # before the threshold is actually crossed.
            should_alert = pred.status != "ideal" or pred.crossing_threshold is not None
            if should_alert:
                alerter.notify(pred, recommend(pred))
            if store:
                store.log_prediction(real_t, pred, should_alert, detector="trend")

        if spiking:
            for pred in spiking.predict_all():
                should_alert = pred.status != "ideal"
                if should_alert:
                    alerter.notify(dataclasses.replace(pred, explanation=f"[spiking] {pred.explanation}"),
                                   recommend(pred))
                if store:
                    store.log_prediction(real_t, pred, should_alert, detector="spiking")

    if store:
        store.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pond health monitor simulation")
    parser.add_argument("--hours", type=float, default=48, help="Simulated hours to run")
    parser.add_argument("--step-minutes", type=float, default=15, help="Simulated minutes per reading")
    parser.add_argument("--scenario", choices=list(SCENARIOS.keys()), default=None)
    parser.add_argument("--scenario-start-hour", type=float, default=6.0)
    parser.add_argument("--scenario-duration-hours", type=float, default=12.0)
    parser.add_argument("--db-path", type=str, default="pond_health.db",
                         help="SQLite file to log readings/predictions to, for Grafana (see grafana/README.md)")
    parser.add_argument("--no-db", action="store_true", help="Skip SQLite logging entirely")
    parser.add_argument("--no-spiking", action="store_true",
                         help="Skip the Spikeling-based anomaly detector (trend predictor only)")
    args = parser.parse_args()

    run(args.hours, args.step_minutes, args.scenario,
        args.scenario_start_hour, args.scenario_duration_hours,
        db_path=None if args.no_db else args.db_path,
        use_spiking=not args.no_spiking)
