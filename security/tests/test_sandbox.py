import shutil
import subprocess
import textwrap

import pytest

from security.sandbox import run_pytest

pytestmark = pytest.mark.skipif(
    shutil.which("docker") is None
    or subprocess.run(["docker", "info"], capture_output=True, check=False).returncode != 0,
    reason="Docker daemon not available",
)


def write_project(root, files: dict[str, str]):
    for name, body in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(body))
    return root


def test_counts_passing_and_failing_tests(tmp_path):
    project = write_project(tmp_path, {
        "calc.py": """
            def add(a, b):
                return a + b
        """,
        "test_calc.py": """
            from calc import add

            def test_add():
                assert add(2, 3) == 5

            def test_add_wrong():
                assert add(2, 2) == 5
        """,
    })

    result = run_pytest(project)

    assert (result.passed, result.failed, result.errors) == (1, 1, 0)


def test_reports_line_coverage_of_project_code(tmp_path):
    project = write_project(tmp_path, {
        "calc.py": """
            def add(a, b):
                return a + b

            def unused(x):
                if x:
                    return 1
                return 2
        """,
        "test_calc.py": """
            from calc import add

            def test_add():
                assert add(1, 1) == 2
        """,
    })

    result = run_pytest(project)

    assert result.coverage_percent is not None
    assert 0 < result.coverage_percent < 100


def test_coverage_can_target_one_module_with_branches(tmp_path):
    project = write_project(tmp_path, {
        "solution.py": """
            def sign(x):
                if x < 0:
                    return -1
                return 1
        """,
        "test_solution.py": """
            from solution import sign

            def test_positive():
                assert sign(5) == 1
        """,
    })

    result = run_pytest(project, coverage="solution")

    # 3 of 4 statements run, 1 of 2 branches taken: (3 + 1) / (4 + 2) = 66.7 %.
    # The fully executed test file must not be counted.
    assert result.coverage_percent == pytest.approx(66.7, abs=0.1)


def test_coverage_can_be_disabled(tmp_path):
    project = write_project(tmp_path, {
        "test_one.py": """
            def test_ok():
                assert True
        """,
    })

    result = run_pytest(project, coverage=False)

    assert result.passed == 1
    assert result.coverage_percent is None


def test_numpy_is_available_for_benchmark_tests(tmp_path):
    project = write_project(tmp_path, {
        "test_np.py": """
            import numpy as np

            def test_allclose():
                assert np.allclose([1.0], [1.0 + 1e-9])
        """,
    })

    result = run_pytest(project, coverage=False)

    assert (result.passed, result.failed, result.errors) == (1, 0, 0), result.output


def run_single_probe(tmp_path, body: str, **kwargs):
    """Run one in-sandbox test; the probe passes only if the sandbox blocks the action."""
    project = write_project(tmp_path, {"test_probe.py": body})
    return run_pytest(project, **kwargs)


def test_blocks_network_access(tmp_path):
    result = run_single_probe(tmp_path, """
        import socket
        import pytest

        def test_outbound_connection_fails():
            with pytest.raises(OSError):
                socket.create_connection(("1.1.1.1", 53), timeout=3)
    """)

    assert (result.passed, result.failed) == (1, 0), result.output


def test_project_files_are_read_only(tmp_path):
    result = run_single_probe(tmp_path, """
        import pytest

        def test_cannot_modify_project():
            with pytest.raises(OSError):
                open("test_probe.py", "a").write("# tampered")
    """)

    assert (result.passed, result.failed) == (1, 0), result.output


def test_runs_as_unprivileged_user(tmp_path):
    result = run_single_probe(tmp_path, """
        import os

        def test_not_root():
            assert os.getuid() != 0
    """)

    assert (result.passed, result.failed) == (1, 0), result.output


def test_stops_tests_that_exceed_timeout(tmp_path):
    result = run_single_probe(tmp_path, """
        import time

        def test_hangs():
            time.sleep(120)
    """, timeout_s=8)

    running = subprocess.run(
        ["docker", "ps", "-q", "--filter", "label=locali.sandbox"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert result.timed_out
    assert result.duration_s < 30
    assert running == ""


def test_limits_memory(tmp_path):
    result = run_single_probe(tmp_path, """
        def test_allocate_one_gib():
            block = bytearray(1024 ** 3)
            assert len(block) == 1024 ** 3
    """)

    assert result.passed == 0, result.output


def test_limits_process_count(tmp_path):
    result = run_single_probe(tmp_path, """
        import os
        import time
        import pytest

        def test_fork_bomb_is_stopped():
            with pytest.raises(OSError):
                for _ in range(1000):
                    if os.fork() == 0:
                        time.sleep(15)
                        os._exit(0)
    """)

    assert (result.passed, result.failed) == (1, 0), result.output


def test_does_not_expose_host_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALI_FAKE_API_KEY", "sk-test-not-real")
    result = run_single_probe(tmp_path, """
        import os

        def test_secret_absent():
            assert "LOCALI_FAKE_API_KEY" not in os.environ
    """)

    assert (result.passed, result.failed) == (1, 0), result.output
