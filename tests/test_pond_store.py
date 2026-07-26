import sqlite3

from prediction.trend_predictor import Prediction
from sensors.sensor_interface import Reading
from storage.pond_store import PondHistoryStore


def _reading(t=1000.0):
    return Reading(
        timestamp=t, temperature_c=22.5, ph=7.2, turbidity_ntu=3.0,
        dissolved_oxygen_mg_l=6.8, conductivity_us_cm=350.0,
    )


def _prediction():
    return Prediction(
        parameter="dissolved_oxygen_mg_l", current_value=6.8, trend_per_hour=-0.1,
        status="ideal", crossing_threshold=None, hours_to_threshold=None,
        explanation="stable",
    )


def test_log_reading_persists_all_fields(tmp_path):
    store = PondHistoryStore(str(tmp_path / "test.db"))
    store.log_reading(1_700_000_000.0, _reading())
    store.close()

    conn = sqlite3.connect(str(tmp_path / "test.db"))
    row = conn.execute("SELECT * FROM readings").fetchone()
    assert row == (1_700_000_000.0, 22.5, 7.2, 3.0, 6.8, 350.0)


def test_log_prediction_persists_alert_flag(tmp_path):
    store = PondHistoryStore(str(tmp_path / "test.db"))
    store.log_prediction(1_700_000_000.0, _prediction(), alerted=True)
    store.close()

    conn = sqlite3.connect(str(tmp_path / "test.db"))
    row = conn.execute("SELECT parameter, status, alerted FROM predictions").fetchone()
    assert row == ("dissolved_oxygen_mg_l", "ideal", 1)


def test_log_prediction_defaults_detector_to_trend(tmp_path):
    store = PondHistoryStore(str(tmp_path / "test.db"))
    store.log_prediction(1_700_000_000.0, _prediction(), alerted=False)
    store.close()

    conn = sqlite3.connect(str(tmp_path / "test.db"))
    row = conn.execute("SELECT detector FROM predictions").fetchone()
    assert row == ("trend",)


def test_log_prediction_records_spiking_detector(tmp_path):
    store = PondHistoryStore(str(tmp_path / "test.db"))
    store.log_prediction(1_700_000_000.0, _prediction(), alerted=True, detector="spiking")
    store.close()

    conn = sqlite3.connect(str(tmp_path / "test.db"))
    row = conn.execute("SELECT detector FROM predictions").fetchone()
    assert row == ("spiking",)


def test_reopening_same_db_path_does_not_wipe_existing_rows(tmp_path):
    db_path = str(tmp_path / "test.db")
    store = PondHistoryStore(db_path)
    store.log_reading(1_700_000_000.0, _reading())
    store.close()

    store2 = PondHistoryStore(db_path)
    store2.log_reading(1_700_000_060.0, _reading(t=1060.0))
    count = store2._conn.execute("SELECT COUNT(*) FROM readings").fetchone()[0]
    store2.close()
    assert count == 2
