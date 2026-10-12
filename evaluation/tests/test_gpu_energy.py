from datetime import datetime

import pytest

from evaluation.gpu_energy import energy_joules, parse_power_log

LOG = """\
2026/10/12 10:00:00.000, 0, 60.00, 1000
2026/10/12 10:00:00.000, 1, 10.00, 100
2026/10/12 10:00:01.000, 0, 80.00, 1000
2026/10/12 10:00:01.000, 1, 10.00, 100
2026/10/12 10:00:02.000, 0, 80.00, 1000
2026/10/12 10:00:02.000, 1, 30.00, 100
"""


def ts(second: int) -> float:
    return datetime(2026, 10, 12, 10, 0, second).astimezone().timestamp()  # local, like nvidia-smi


def test_parses_samples_per_gpu():
    samples = parse_power_log(LOG)
    assert [s.watts for s in samples if s.gpu == 0] == [60.0, 80.0, 80.0]


def test_integrates_power_of_selected_gpu_over_window():
    # trapezoid: (60+80)/2 * 1 s + (80+80)/2 * 1 s = 150 J
    assert energy_joules(parse_power_log(LOG), gpus=[0], start=ts(0), end=ts(2)) == pytest.approx(150.0)


def test_sums_several_gpus():
    # gpu 1: (10+10)/2 + (10+30)/2 = 30 J
    assert energy_joules(parse_power_log(LOG), gpus=[0, 1], start=ts(0), end=ts(2)) == pytest.approx(180.0)


def test_only_counts_samples_inside_the_window():
    assert energy_joules(parse_power_log(LOG), gpus=[0], start=ts(1), end=ts(2)) == pytest.approx(80.0)


def test_returns_none_without_samples():
    assert energy_joules([], gpus=[0], start=ts(0), end=ts(2)) is None


def test_attach_writes_gpu_energy_into_run_summary(tmp_path):
    import json

    from evaluation.gpu_energy import attach_gpu_energy

    run = tmp_path / "run"
    run.mkdir()
    (run / "summary.json").write_text(json.dumps({"metrics": {"n": 3}}))

    attach_gpu_energy(run, LOG, gpus=[0, 1], start=ts(0), end=ts(2))

    saved = json.loads((run / "summary.json").read_text())["gpu_energy"]
    assert saved["total_j"] == pytest.approx(180.0)
    assert saved["j_per_task"] == pytest.approx(60.0)
    assert saved["gpus"] == [0, 1]
