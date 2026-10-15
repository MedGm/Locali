from pathlib import Path

from backend.agents.testgen import generate_tests, untested_functions
from backend.tests.test_debug_agent import ScriptedModel
from backend.workspace import open_workspace
from evaluation.tests.test_codegen import needs_docker

DEMO = Path(__file__).resolve().parents[2] / "demo_repo"

BULK_TESTS = """```python
from solution import bulk_discount


def test_small_order():
    assert bulk_discount(5) == 0


def test_fifty_units():
    # the comment in the code says 10% from 50 units
    assert bulk_discount(50) == 10
```"""


def test_untested_functions_are_the_repo_functions_no_test_mentions():
    found = untested_functions(DEMO)
    assert ("tinyshop/pricing.py", "bulk_discount") in found
    assert ("tinyshop/inventory.py", "total_units") in found
    assert ("tinyshop/pricing.py", "apply_discount") not in found  # used in tests/test_pricing.py
    assert not any(path.startswith("tests/") for path, _ in found)


@needs_docker
def test_passing_tests_are_kept_and_failing_ones_become_suspects():
    ws = open_workspace(DEMO)
    try:
        model = ScriptedModel(BULK_TESTS)
        result = generate_tests(ws.path, model, [("tinyshop/pricing.py", "bulk_discount")])
        assert "from solution import bulk_discount" in model.prompts[0]

        kept = (ws.path / result.files[0]).read_text()
        assert "from tinyshop.pricing import" in kept and "solution" not in kept
        assert "def test_small_order" in kept and "def test_fifty_units" not in kept

        [suspect] = result.suspects
        assert suspect.function == "bulk_discount" and "test_fifty_units" in suspect.test
        assert "5 == 10" in suspect.error
        assert not (DEMO / result.files[0]).exists()
    finally:
        ws.cleanup()


@needs_docker
def test_unusable_answer_adds_nothing():
    ws = open_workspace(DEMO)
    try:
        result = generate_tests(ws.path, ScriptedModel("I cannot help with that."),
                                [("tinyshop/pricing.py", "bulk_discount")])
        assert result.files == [] and result.suspects == []
        assert ws.diff() == ""
    finally:
        ws.cleanup()


CRASHING_TESTS = """```python
from solution import bulk_discount


def test_needs_a_fixture():
    conn = None
    conn.execute("select 1")
    assert bulk_discount(5) == 0


def test_fifty_units():
    assert bulk_discount(50) == 10
```"""


@needs_docker
def test_tests_that_crash_are_counted_not_reported_as_suspects():
    ws = open_workspace(DEMO)
    try:
        result = generate_tests(ws.path, ScriptedModel(CRASHING_TESTS), [("tinyshop/pricing.py", "bulk_discount")])
        assert [s.test.splitlines()[0] for s in result.suspects] == ["def test_fifty_units():"]
        assert result.crashed == {"tinyshop/pricing.py::bulk_discount": 1}
        assert result.files == []
    finally:
        ws.cleanup()
