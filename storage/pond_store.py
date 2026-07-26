"""SQLite persistence for readings + predictions.

The point of this module is entirely to give Grafana something to point
at: SQLite needs no separate database server to install/run, and the
free `frser-sqlite-datasource` Grafana plugin can query a .db file
directly. See grafana/README.md for the dashboard setup.
"""
import sqlite3
from typing import Optional

from prediction.trend_predictor import Prediction
from sensors.sensor_interface import Reading

_SCHEMA = """
CREATE TABLE IF NOT EXISTS readings (
    timestamp REAL NOT NULL,
    temperature_c REAL NOT NULL,
    ph REAL NOT NULL,
    turbidity_ntu REAL NOT NULL,
    dissolved_oxygen_mg_l REAL NOT NULL,
    conductivity_us_cm REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_readings_timestamp ON readings(timestamp);

CREATE TABLE IF NOT EXISTS predictions (
    timestamp REAL NOT NULL,
    parameter TEXT NOT NULL,
    current_value REAL NOT NULL,
    trend_per_hour REAL NOT NULL,
    status TEXT NOT NULL,
    crossing_threshold TEXT,
    hours_to_threshold REAL,
    explanation TEXT NOT NULL,
    alerted INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_predictions_timestamp ON predictions(timestamp);
"""


class PondHistoryStore:
    def __init__(self, db_path: str = "pond_health.db"):
        self._conn = sqlite3.connect(db_path)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    def log_reading(self, timestamp: float, reading: Reading) -> None:
        """`timestamp` is a real (wall-clock) unix-epoch seconds value --
        kept separate from `reading.timestamp`, which is simulated-clock
        seconds-from-run-start and meaningless as a calendar date."""
        self._conn.execute(
            "INSERT INTO readings (timestamp, temperature_c, ph, turbidity_ntu, "
            "dissolved_oxygen_mg_l, conductivity_us_cm) VALUES (?, ?, ?, ?, ?, ?)",
            (
                timestamp,
                reading.temperature_c,
                reading.ph,
                reading.turbidity_ntu,
                reading.dissolved_oxygen_mg_l,
                reading.conductivity_us_cm,
            ),
        )
        self._conn.commit()

    def log_prediction(self, timestamp: float, pred: Prediction, alerted: bool) -> None:
        self._conn.execute(
            "INSERT INTO predictions (timestamp, parameter, current_value, "
            "trend_per_hour, status, crossing_threshold, hours_to_threshold, "
            "explanation, alerted) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                timestamp,
                pred.parameter,
                pred.current_value,
                pred.trend_per_hour,
                pred.status,
                pred.crossing_threshold,
                pred.hours_to_threshold,
                pred.explanation,
                int(alerted),
            ),
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()
