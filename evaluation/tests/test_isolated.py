import os

import pytest

from evaluation.isolated import run_isolated

NET = os.geteuid() == 0  # network isolation needs root (as on Kaggle); the rest is tested everywhere


def test_a_passing_program_passes():
    assert run_isolated("assert 1 + 1 == 2\n", isolate_network=NET).passed


def test_a_failing_assert_reports_its_message():
    r = run_isolated("def f():\n    return 1\nassert f() == 2, 'f() returned 1, expected 2'\n", isolate_network=NET)
    assert not r.passed and r.status == "failed" and r.error == "AssertionError: f() returned 1, expected 2"


def test_endless_loops_time_out():
    r = run_isolated("while True:\n    pass\n", timeout_s=2, isolate_network=NET)
    assert r.status == "timeout" and not r.passed


def test_memory_is_limited():
    r = run_isolated("x = bytearray(4 * 1024 ** 3)\n", memory_mb=512, isolate_network=NET)
    assert not r.passed and "MemoryError" in r.error


def test_the_program_runs_in_its_own_empty_folder_without_inherited_secrets(monkeypatch):
    monkeypatch.setenv("LOCALI_MODEL_KEY", "secret-value")
    r = run_isolated("import os\nassert os.listdir('.') == ['candidate.py'], os.listdir('.')\n"
                     "assert 'LOCALI_MODEL_KEY' not in os.environ\n", isolate_network=NET)
    assert r.passed, r.error


@pytest.mark.skipif(not NET, reason="network isolation needs root")
def test_no_network_when_isolated():
    r = run_isolated("import socket\nsocket.create_connection(('1.1.1.1', 53), timeout=3)\n", isolate_network=True)
    assert not r.passed
