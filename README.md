# Pond Health

Predicts pond water-quality problems before they're visible, and
recommends organic fixes — a weather forecast for your pond instead of
a snapshot of it.

**Status: software prototype.** No physical sensors are wired up yet.
The pipeline runs end-to-end today against a realistic simulator so the
prediction/diagnosis logic can be built and verified now; swapping in
real hardware later only requires writing one new class (see
[Going physical](#going-physical) below) — nothing else in the project
changes.

## What it does

1. **Reads** water-quality sensors (temperature, pH, turbidity,
   dissolved oxygen, conductivity) on an interval.
2. **Predicts** where each parameter is headed by fitting a trend line
   to recent readings and projecting it forward — e.g. *"dissolved
   oxygen is falling 0.8 mg/L per hour and will cross the danger
   threshold in about 3 hours."*
3. **Diagnoses** the specific deficiency (low oxygen, algae risk, pH
   swing, turbidity spike, conductivity/contamination) against
   established aquaculture thresholds.
4. **Recommends** a concrete organic fix for each one (add aeration,
   introduce oxygenating plants, buffer pH with crushed coral, add a
   barley-straw flocculant, etc.) and prints an alert.

This is intentionally **not** a black-box ML model. There's no real
historical pond data yet to train one honestly, so v1 reasons the way an
experienced pond keeper would — trend + threshold, plainly explained.
Once you're logging real sensor history, swap `trend_predictor.py`'s
linear fit for a trained model (scikit-learn `RandomForestRegressor`, an
LSTM, etc.) without touching the diagnosis or alert layers; they only
depend on the `Prediction` shape it returns.

## Try it

```bash
pip install -r requirements.txt

# Normal 48-hour day/night cycle, nothing wrong
python main.py

# Force a specific problem to develop, to see the prediction/diagnosis
# layer catch it in advance:
python main.py --scenario night_oxygen_crash
python main.py --scenario algae_bloom_developing --hours 72
python main.py --scenario ammonia_buildup
python main.py --scenario runoff_turbidity_spike
```

Run the tests:

```bash
pytest
```

## Architecture

```
sensors/       Reading data shape + SensorReader interface.
               simulated_reader.py generates physically-grounded fake
               data (real diurnal temp/DO cycles, day/night
               photosynthesis, temperature-linked DO saturation
               ceiling) with injectable "scenarios" for testing.

prediction/    thresholds.py: established aquaculture safe/stress/
               critical ranges per parameter.
               trend_predictor.py: fits a trend per parameter and
               projects forward to "hours until threshold crossed."

diagnosis/     organic_fixes.py: maps a Prediction's (parameter,
               status) to a list of concrete organic remedies.

alerts/        console_alerter.py: prints readable warnings. Swap in
               an email/SMS/webhook sender later using the same
               notify(prediction, fixes) shape.

main.py        Wires the pipeline together and runs the simulation.
```

## Going physical

When you're ready to attach real sensors, everything below plugs into
the existing pipeline unchanged — only `sensors/` needs a new file.

**Estimated hardware cost for a small (5x5m) pond: ~$600–$1,000.**

| Component | Role | Est. cost |
|---|---|---|
| DS18B20 | Water temperature | ~$2 |
| pH probe (e.g. SEN0161) | Acidity/alkalinity | ~$14 |
| EC/TDS probe (e.g. SEN0244) | Conductivity | ~$12 |
| Turbidity sensor | Water clarity | ~$15–30 |
| Dissolved oxygen probe | Oxygen level (the most critical one) | ~$150–400 |
| ESP32 or Raspberry Pi | Reads sensors, runs this code | $6–$100 |
| Waterproof enclosure + cabling | Protects electronics | ~$30–50 |
| Wi-Fi / LoRa module (optional) | Remote alerting | ~$0–30 |
| Small solar panel + battery (optional) | Untethered power | ~$50–100 |

To go physical: implement a new `SensorReader` subclass (see
`sensors/sensor_interface.py`) that reads the real probes over
serial/I2C/ADC and returns a `Reading`, then point `main.py` at it
instead of `SimulatedPondReader`. Everything downstream — prediction,
diagnosis, alerting — needs no changes.
