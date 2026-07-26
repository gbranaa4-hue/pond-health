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

from sensors.simulated_reader import SimulatedPondReader, Scenario
from prediction.trend_predictor import TrendPredictor
from diagnosis.organic_fixes import recommend
from alerts.console_alerter import ConsoleAlerter

SCENARIOS = {
    "algae_bloom_developing": Scenario.ALGAE_BLOOM_DEVELOPING,
    "night_oxygen_crash": Scenario.NIGHT_OXYGEN_CRASH,
    "ammonia_buildup": Scenario.AMMONIA_BUILDUP,
    "runoff_turbidity_spike": Scenario.RUNOFF_TURBIDITY_SPIKE,
}


def run(hours: float, step_minutes: float, scenario: str = None,
        scenario_start_hour: float = 6.0, scenario_duration_hours: float = 12.0) -> None:
    reader = SimulatedPondReader(start_time=0.0)
    predictor = TrendPredictor()
    alerter = ConsoleAlerter()

    if scenario:
        reader.start_scenario(
            SCENARIOS[scenario],
            duration_s=scenario_duration_hours * 3600,
            at_time=scenario_start_hour * 3600,
        )

    step_s = step_minutes * 60
    total_steps = int(hours * 3600 / step_s)

    for i in range(total_steps):
        now = i * step_s
        reading = reader.read(at_time=now)
        predictor.ingest(reading)

        hh = int((now / 3600) % 24)
        print(f"\n--- t={now / 3600:.1f}h (hour {hh:02d}:00) ---")
        print(
            f"  temp={reading.temperature_c}C  pH={reading.ph}  "
            f"turbidity={reading.turbidity_ntu}NTU  DO={reading.dissolved_oxygen_mg_l}mg/L  "
            f"EC={reading.conductivity_us_cm}uS/cm"
        )

        for pred in predictor.predict_all():
            # Alert if it's already a problem, OR if the trend says it's
            # headed for one -- the whole point of prediction is warning
            # before the threshold is actually crossed.
            if pred.status != "ideal" or pred.crossing_threshold is not None:
                alerter.notify(pred, recommend(pred))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pond health monitor simulation")
    parser.add_argument("--hours", type=float, default=48, help="Simulated hours to run")
    parser.add_argument("--step-minutes", type=float, default=15, help="Simulated minutes per reading")
    parser.add_argument("--scenario", choices=list(SCENARIOS.keys()), default=None)
    parser.add_argument("--scenario-start-hour", type=float, default=6.0)
    parser.add_argument("--scenario-duration-hours", type=float, default=12.0)
    args = parser.parse_args()

    run(args.hours, args.step_minutes, args.scenario,
        args.scenario_start_hour, args.scenario_duration_hours)
