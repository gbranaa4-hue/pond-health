from sensors.simulated_reader import SimulatedPondReader, Scenario, do_saturation_mg_l


def test_do_saturation_decreases_with_temperature():
    assert do_saturation_mg_l(10.0) > do_saturation_mg_l(30.0)


def test_do_saturation_reasonable_at_room_temp():
    assert 7.0 < do_saturation_mg_l(20.0) < 10.0


def test_reader_produces_reading_in_valid_ranges():
    reader = SimulatedPondReader(start_time=0.0)
    reading = reader.read(at_time=3600 * 14)
    assert 0.0 <= reading.ph <= 14.0
    assert reading.turbidity_ntu >= 0.0
    assert reading.dissolved_oxygen_mg_l >= 0.0
    assert reading.conductivity_us_cm >= 0.0


def test_night_oxygen_crash_scenario_lowers_do():
    # Compare the SAME timestamp with and without the scenario active --
    # DO naturally varies by time of day too, so a fair test needs to
    # hold that constant and isolate the scenario's effect.
    check_time = 3600 * 6

    baseline_reader = SimulatedPondReader(start_time=0.0)
    baseline = baseline_reader.read(at_time=check_time).dissolved_oxygen_mg_l

    crash_reader = SimulatedPondReader(start_time=0.0)
    crash_reader.start_scenario(Scenario.NIGHT_OXYGEN_CRASH, duration_s=3600 * 6, at_time=0.0)
    crashed = crash_reader.read(at_time=check_time).dissolved_oxygen_mg_l

    assert crashed < baseline
    assert crashed < 2.0
