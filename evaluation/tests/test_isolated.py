
from evaluation.isolated import network_isolation, run_isolated

NET = "none"  # network isolation is tested on its own below


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


CONNECT = "import socket\nsocket.create_connection(('1.1.1.1', 53), timeout=3)\n"


def test_the_guard_blocks_sockets():
    r = run_isolated(CONNECT, isolate_network="guard")
    assert not r.passed and "network disabled" in r.error


def test_auto_picks_a_working_method_and_says_which():
    mode = network_isolation()
    assert mode in ("namespace", "guard")
    assert not run_isolated(CONNECT, isolate_network="auto").passed
