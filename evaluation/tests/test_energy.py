import pytest

from evaluation.energy import RaplMeter


@pytest.fixture
def counter(tmp_path):
    energy = tmp_path / "energy_uj"
    max_range = tmp_path / "max_energy_range_uj"
    max_range.write_text("10000000\n")
    return energy, max_range


def test_measures_joules_between_readings(counter):
    energy, max_range = counter
    energy.write_text("1000000\n")
    meter = RaplMeter(energy, max_range)

    with meter.measure() as m:
        energy.write_text("3500000\n")

    assert m.joules == pytest.approx(2.5)


def test_handles_counter_wraparound(counter):
    energy, max_range = counter
    energy.write_text("9000000\n")
    meter = RaplMeter(energy, max_range)

    with meter.measure() as m:
        energy.write_text("500000\n")

    assert m.joules == pytest.approx(1.5)


def test_reports_none_when_counter_unreadable(tmp_path):
    meter = RaplMeter(tmp_path / "missing_energy_uj", tmp_path / "missing_max")

    with meter.measure() as m:
        pass

    assert meter.available is False
    assert m.joules is None
