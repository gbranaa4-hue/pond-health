"""Builds grafana/dashboard.json from prediction/thresholds.py, so the
dashboard's color zones always match what the app actually alerts on --
not a hand-copied set of numbers that can drift out of sync.

Re-run this whenever thresholds.py changes:
    python grafana/generate_dashboard.py

Requires the "SQLite" datasource (fr-ser/grafana-sqlite-datasource
plugin) added in Grafana first; import prompts for it as "DS_SQLITE".
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from prediction.thresholds import THRESHOLDS, Range  # noqa: E402

UNITS = {
    "temperature_c": "celsius",
    "ph": "none",
    "turbidity_ntu": "none",
    "dissolved_oxygen_mg_l": "none",
    "conductivity_us_cm": "none",
}
SUFFIXES = {
    "ph": "",
    "turbidity_ntu": " NTU",
    "dissolved_oxygen_mg_l": " mg/L",
    "conductivity_us_cm": " uS/cm",
}
TITLES = {
    "temperature_c": "Temperature",
    "ph": "pH",
    "turbidity_ntu": "Turbidity",
    "dissolved_oxygen_mg_l": "Dissolved Oxygen",
    "conductivity_us_cm": "Conductivity",
}
PARAM_ORDER = [
    "temperature_c", "ph", "dissolved_oxygen_mg_l",
    "turbidity_ntu", "conductivity_us_cm",
]


def build_threshold_steps(rng: Range):
    """Mirrors prediction/trend_predictor.py's _classify() exactly --
    that function only ever looks at critical_low/stress_low/
    stress_high/critical_high, so the dashboard's color zones are built
    from the same four cutoffs (not ideal_low/ideal_high, which
    `_classify` doesn't actually use)."""
    lows = [(name, getattr(rng, name)) for name in ("critical_low", "stress_low")
            if getattr(rng, name) is not None]
    highs = [(name, getattr(rng, name)) for name in ("stress_high", "critical_high")
             if getattr(rng, name) is not None]
    lows.sort(key=lambda x: x[1])
    highs.sort(key=lambda x: x[1])

    steps = []
    if lows:
        base_color = "red" if lows[0][0] == "critical_low" else "orange"
    else:
        base_color = "green"
    steps.append({"value": None, "color": base_color})

    for name, val in lows:
        color = ("orange" if len(lows) > 1 else "green") if name == "critical_low" else "green"
        steps.append({"value": val, "color": color})

    for name, val in highs:
        color = "orange" if name == "stress_high" else "red"
        steps.append({"value": val, "color": color})

    return steps


def _panel(param: str, panel_id: int, x: int, y: int):
    rng = THRESHOLDS[param]
    return {
        "id": panel_id,
        "gridPos": {"h": 8, "w": 12, "x": x, "y": y},
        "title": TITLES[param],
        "type": "timeseries",
        "datasource": {"type": "frser-sqlite-datasource", "uid": "${DS_SQLITE}"},
        "targets": [{
            "refId": "A",
            "queryType": "time series",
            "timeColumns": ["time"],
            "queryText": (
                f"SELECT timestamp * 1000 AS time, {param} AS value "
                f"FROM readings ORDER BY time"
            ),
            "rawQueryText": (
                f"SELECT timestamp * 1000 AS time, {param} AS value "
                f"FROM readings ORDER BY time"
            ),
        }],
        "fieldConfig": {
            "defaults": {
                "unit": UNITS[param],
                "custom": {
                    "drawStyle": "line",
                    "lineWidth": 2,
                    "fillOpacity": 10,
                    "thresholdsStyle": {"mode": "area"},
                },
                "thresholds": {"mode": "absolute", "steps": build_threshold_steps(rng)},
            },
            "overrides": [],
        },
        "options": {"legend": {"displayMode": "list", "placement": "bottom"}},
    }


def _alerts_table_panel(panel_id: int, x: int, y: int):
    return {
        "id": panel_id,
        "gridPos": {"h": 8, "w": 24, "x": x, "y": y},
        "title": "Alerts (forecast + active)",
        "type": "table",
        "datasource": {"type": "frser-sqlite-datasource", "uid": "${DS_SQLITE}"},
        "targets": [{
            "refId": "A",
            "queryType": "table",
            "timeColumns": ["time"],
            "queryText": (
                "SELECT timestamp * 1000 AS time, parameter, status, "
                "current_value, hours_to_threshold, explanation "
                "FROM predictions WHERE alerted = 1 ORDER BY time DESC LIMIT 200"
            ),
            "rawQueryText": (
                "SELECT timestamp * 1000 AS time, parameter, status, "
                "current_value, hours_to_threshold, explanation "
                "FROM predictions WHERE alerted = 1 ORDER BY time DESC LIMIT 200"
            ),
        }],
        "fieldConfig": {"defaults": {}, "overrides": []},
        "options": {},
    }


def build_dashboard():
    panels = []
    panel_id = 1
    for i, param in enumerate(PARAM_ORDER):
        x = 12 * (i % 2)
        y = 8 * (i // 2)
        panels.append(_panel(param, panel_id, x, y))
        panel_id += 1

    alerts_y = 8 * ((len(PARAM_ORDER) + 1) // 2)
    panels.append(_alerts_table_panel(panel_id, 0, alerts_y))

    return {
        "__inputs": [{
            "name": "DS_SQLITE",
            "label": "SQLite",
            "description": "Add the SQLite datasource (fr-ser/grafana-sqlite-datasource plugin) pointing at pond_health.db before importing.",
            "type": "datasource",
            "pluginId": "frser-sqlite-datasource",
            "pluginName": "SQLite",
        }],
        "title": "Pond Health",
        "uid": "pond-health",
        "timezone": "browser",
        "schemaVersion": 39,
        "version": 1,
        "refresh": "1m",
        "time": {"from": "now-24h", "to": "now"},
        "panels": panels,
    }


if __name__ == "__main__":
    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard.json")
    with open(out_path, "w") as f:
        json.dump(build_dashboard(), f, indent=2)
    print(f"Wrote {out_path}")
