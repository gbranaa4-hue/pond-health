# Grafana dashboard

`main.py` logs every reading and prediction to a local SQLite file
(`pond_health.db` by default — see `--db-path`/`--no-db`). Grafana can
visualize that file directly with the free **SQLite datasource plugin**,
no separate database server (InfluxDB, Prometheus, etc.) required.

## 1. Install Grafana

Download from [grafana.com/grafana/download](https://grafana.com/grafana/download)
(Windows: the standalone installer is simplest) and start it — it runs
as a local web app, by default at `http://localhost:3000` (default
login `admin` / `admin`, it'll prompt you to change it).

## 2. Install the SQLite datasource plugin

```bash
grafana-cli plugins install frser-sqlite-datasource
```
Then restart the Grafana service. (On Windows, restart it from
Services, or just restart the Grafana app if you ran it standalone.)

## 3. Add the datasource

In Grafana: **Connections → Data sources → Add data source → SQLite**.
Set **Path** to the full path of `pond_health.db` (e.g.
`C:\Users\<you>\Documents\pond-health\pond_health.db`) — the file has
to exist already, so run a scenario at least once first:
```bash
python main.py --scenario algae_bloom_developing --hours 24
```

## 4. Import the dashboard

**Dashboards → New → Import**, upload
[`dashboard.json`](dashboard.json), and when prompted for the "SQLite"
datasource input, pick the one you just created.

If the import has any hiccups (dashboard JSON schemas shift between
Grafana versions/plugin builds), it's just as fast to build the panels
by hand — Add panel → SQLite datasource → paste one of these:

```sql
-- Temperature / pH / Dissolved Oxygen / Turbidity / Conductivity (time series)
SELECT timestamp * 1000 AS time, temperature_c AS value FROM readings ORDER BY time;
SELECT timestamp * 1000 AS time, ph AS value FROM readings ORDER BY time;
SELECT timestamp * 1000 AS time, dissolved_oxygen_mg_l AS value FROM readings ORDER BY time;
SELECT timestamp * 1000 AS time, turbidity_ntu AS value FROM readings ORDER BY time;
SELECT timestamp * 1000 AS time, conductivity_us_cm AS value FROM readings ORDER BY time;

-- Alerts (table) -- "detector" is 'trend' or 'spiking', see main README's
-- "Two anomaly detectors" section for what that distinction means
SELECT timestamp * 1000 AS time, detector, parameter, status, current_value,
       hours_to_threshold, explanation
FROM predictions WHERE alerted = 1 ORDER BY time DESC LIMIT 200;
```

## Regenerating the dashboard

`dashboard.json` is generated, not hand-written — its panel color
thresholds are pulled straight from `prediction/thresholds.py` so they
can't drift out of sync with what the app actually alerts on. If you
change a threshold, regenerate it:
```bash
python grafana/generate_dashboard.py
```

## Notes

- Each run of `main.py` "replays" its simulated hours ending at the
  real current time (see `main.py`'s `wall_now` anchoring), so Grafana's
  default relative time ranges (last 24h, last 7d) show the run
  immediately without picking a custom range.
- Running `main.py` again with the same `--db-path` appends to the same
  database rather than overwriting it, so multiple runs build up
  history in the same dashboard.
