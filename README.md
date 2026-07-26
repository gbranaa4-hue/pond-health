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

## Two anomaly detectors

`main.py` runs a second, genuinely different detector alongside the
trend predictor: a **spiking neural network**, built on the real
[Spikeling](https://github.com/gbranaa4-hue/Spikeling) engine (the same
DSL/runtime that drives NPC brains in `tribe` and a live Arduino sensor
grid) rather than a one-off reimplementation. See
`prediction/pond_brain.spk` and `prediction/spiking_predictor.py`.

Each parameter drives its own LIF neuron with a "stress current" — zero
at an ideal reading (so a single noisy blip can't trip it), and enough
to fire only once several consecutive stressed readings integrate past
threshold, or instantly under a genuinely critical reading. It doesn't
forecast the future the way the trend predictor does; it answers a
different question — *has this been a real, sustained problem, or
noise?* — and both log to the same SQLite file (`detector` column:
`trend` or `spiking`) so Grafana's alerts table shows whether they
agree.

**Honestly measured, not assumed** — running both against the bundled
scenarios (`--hours 24`) surfaced a real difference, not just a
theoretical one:

| Scenario | Trend alerts | Spiking alerts | What actually happened |
|---|---|---|---|
| `night_oxygen_crash` | 91 (60 real stress/critical + 31 forward-looking forecasts) | 53 | Both correctly caught the real DO crash; spiking produced fewer, less-spammy alerts (fires periodically, not every single step) but with no early warning — trend flagged it up to hours ahead. |
| `runoff_turbidity_spike` | 103 | 31 | Same pattern — spiking confirms the sustained problem, trend gets there earlier. |
| `algae_bloom_developing` | 78 (all 78 were forecasts — turbidity peaked at 43.9, never actually reached the stress_high=50 line in this run) | 0 | Spiking stayed silent because, by design, it only reacts to a *confirmed* crossing — it doesn't get credit (or blame) for a threshold that technically never got crossed. Whether those 78 trend forecasts were "right to warn early" or "false alarms for a crossing that didn't happen" depends on your risk tolerance, and this run can't tell you which. |
| `ammonia_buildup` | 94 | 0 | Same story as the algae case — no parameter actually crosses a real zone boundary in this scenario at 24h. |

Net honest takeaway: the trend predictor trades false-alarm risk for
early warning; the spiking detector trades early warning for only ever
alerting on a confirmed, sustained problem. Neither is strictly better —
run both and let the alerts table show you where they disagree.

**Setup:** clone Spikeling as a sibling directory next to this
checkout (`git clone https://github.com/gbranaa4-hue/Spikeling` in the
same parent folder), or set `SPIKELING_CORE_PATH` to point at its
`core/` folder. If it's not found, `main.py` prints a warning and
carries on with the trend predictor alone — this is an optional add-on,
not a hard dependency. Skip it explicitly with `--no-spiking`.

## Visualizing it with Grafana

Every run logs readings and predictions to a local SQLite file
(`pond_health.db` by default). Point Grafana's free SQLite datasource
plugin at it for a real dashboard — temperature/pH/DO/turbidity/
conductivity over time, color-zoned by the same thresholds the app
alerts on, plus a table of every alert that fired. See
[grafana/README.md](grafana/README.md) for the full setup (~10 minutes)
and a ready-to-import [dashboard.json](grafana/dashboard.json).

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
               spiking_predictor.py + pond_brain.spk: the alternate
               Spikeling-based detector -- see "Two anomaly detectors"
               above.

diagnosis/     organic_fixes.py: maps a Prediction's (parameter,
               status) to a list of concrete organic remedies.

alerts/        console_alerter.py: prints readable warnings. Swap in
               an email/SMS/webhook sender later using the same
               notify(prediction, fixes) shape.

storage/       pond_store.py: logs every reading/prediction to SQLite
               for Grafana (or anything else) to query.

grafana/       dashboard.json (generated) + generate_dashboard.py +
               setup instructions -- see "Visualizing it with Grafana"
               above.

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
