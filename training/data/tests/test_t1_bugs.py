import json
import shutil
import subprocess

import pytest

from training.data.t1_bugs import build_examples, failing_test_details, select_seeds

docker_ok = shutil.which("docker") is not None and subprocess.run(
    ["docker", "info"], capture_output=True, check=False
).returncode == 0
needs_docker = pytest.mark.skipif(not docker_ok, reason="Docker daemon not available")

CODE = "def clamp(x, lo, hi):\n    if x < lo:\n        return lo\n    if x > hi:\n        return hi\n    return x\n"
SUITE = '''import unittest

class TestClamp(unittest.TestCase):
    def test_inside(self):
        self.assertEqual(clamp(5, 0, 10), 5)

    def test_low(self):
        self.assertEqual(clamp(-1, 0, 10), 0)

    def test_high(self):
        self.assertEqual(clamp(11, 0, 10), 10)

    def test_edges(self):
        self.assertEqual(clamp(0, 0, 10), 0)
        self.assertEqual(clamp(10, 0, 10), 10)
'''


def row(task_id, code=CODE, suites=None):
    suites = suites or [{"ut_id": 0, "code": SUITE, "FAR": 0.1, "FRR": 0.0}]
    return {"task_id": task_id, "question": "q", "code_ground_truth": code, "unit_tests": json.dumps(suites)}


def test_select_seeds_keeps_parseable_short_functions_with_a_zero_frr_suite():
    rows = [
        row(1),
        row(2, code="def broken(:\n"),
        row(3, code="def long():\n" + "    x = 1\n" * 60),
        row(4, suites=[{"ut_id": 0, "code": SUITE, "FAR": 0.0, "FRR": 0.2}]),
    ]

    seeds = select_seeds(rows, n=10)

    assert [s.task_id for s in seeds] == ["1"]


def test_select_seeds_prefers_the_suite_with_lowest_far():
    suites = [{"ut_id": 0, "code": "A", "FAR": 0.3, "FRR": 0.0}, {"ut_id": 1, "code": SUITE, "FAR": 0.05, "FRR": 0.0}]
    assert select_seeds([row(1, suites=suites)], n=1)[0].tests == SUITE


def test_select_seeds_is_deterministic():
    rows = [row(i) for i in range(50)]
    assert [s.task_id for s in select_seeds(rows, n=10)] == [s.task_id for s in select_seeds(rows, n=10)]


def test_failing_test_details_reads_pytest_output():
    output = (
        "FAILED test_suite.py::TestClamp::test_edges - AssertionError: 10 != 9\n"
        "____ TestClamp.test_edges ____\n"
        "E       AssertionError: 10 != 9\n"
    )
    name, error = failing_test_details(output)
    assert name == "TestClamp::test_edges"
    assert "AssertionError: 10 != 9" in error


@needs_docker
def test_build_examples_keeps_only_mutants_that_fail_a_test():
    seeds = select_seeds([row(1)], n=1)

    examples, stats = build_examples(seeds, mutants_per_seed=2)

    assert len(examples) == 2
    for ex in examples:
        assert ex["fixed_code"] == CODE
        assert ex["buggy_code"] != CODE
        assert ex["failing_test"]["name"].startswith("TestClamp::test_")
        assert "def test_" in ex["failing_test"]["code"]
        assert ex["failing_test"]["error"]
    assert stats["seeds_used"] == 1


@needs_docker
def test_build_examples_skips_seeds_whose_original_fails_its_tests():
    wrong = CODE.replace("return hi", "return hi + 1")

    examples, stats = build_examples(select_seeds([row(1, code=wrong)], n=1), mutants_per_seed=2)

    assert examples == []
    assert stats["seeds_original_failed"] == 1


def test_failing_test_details_keeps_only_the_first_failures_error():
    output = (
        "___________________ TestClamp.test_edges ___________________\n"
        "E       AssertionError: 10 != 9\n"
        "___________________ TestClamp.test_high ___________________\n"
        "E       AssertionError: 11 != 10\n"
        "FAILED test_suite.py::TestClamp::test_edges - AssertionError: 10 != 9\n"
        "FAILED test_suite.py::TestClamp::test_high - AssertionError: 11 != 10\n"
    )
    name, error = failing_test_details(output)
    assert name == "TestClamp::test_edges"
    assert error == "AssertionError: 10 != 9"


def test_round_robin_interleaves_operators_keeping_their_order():
    from training.data.mutate import Mutant
    from training.data.t1_bugs import _round_robin

    ms = [Mutant(op, i, "", "", "") for i, op in enumerate(["a", "a", "a", "b", "c", "b"])]
    assert [(m.operator, m.line) for m in _round_robin(ms)] == [("a", 0), ("b", 3), ("c", 4), ("a", 1), ("b", 5), ("a", 2)]
