import ast

from training.data.t1_bugs import Seed
from training.data.t2_tests import build_t2_examples, t2_messages
from training.data.tests.test_t1_bugs import CODE, needs_docker

SUITE = '''import unittest

class TestClamp(unittest.TestCase):
    def test_inside(self):
        self.assertEqual(clamp(5, 0, 10), 5)

    def test_inside_again(self):
        self.assertEqual(clamp(6, 0, 10), 6)

    def test_low(self):
        self.assertEqual(clamp(-1, 0, 10), 0)

    def test_high(self):
        self.assertEqual(clamp(11, 0, 10), 10)

    def test_edges(self):
        self.assertEqual(clamp(0, 0, 10), 0)
        self.assertEqual(clamp(10, 0, 10), 10)
'''


@needs_docker
def test_selected_tests_catch_mutants_and_pass_on_original():
    examples, _ = build_t2_examples([Seed("1", "q", CODE, SUITE)])

    assert len(examples) == 1
    ex = examples[0]
    tree = ast.parse(ex["tests"])
    names = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]
    assert 3 <= len(names) <= 8
    assert ex["mutants_killed"] >= 1
    assert ex["tests"].count("from solution import") == 1
    assert "from solution import clamp\n" in ex["tests"]
    assert "#" not in ex["tests"]
    assert ex["entry_point"] == "clamp"


@needs_docker
def test_suites_that_catch_no_mutant_are_dropped():
    # calls clamp but checks nothing that a single-fault mutant could change
    weak = "import unittest\n\nclass T(unittest.TestCase):\n    def test_runs(self):\n        self.assertIsNotNone(clamp(5, 0, 10))\n"

    examples, stats = build_t2_examples([Seed("1", "q", CODE, weak)])

    assert examples == []
    assert stats["seeds_weak_suite"] == 1


def test_messages_use_the_shared_testgen_prompt_and_a_code_block_answer():
    example = {"entry_point": "clamp", "code": CODE, "tests": "import pytest\n\ndef test_a():\n    assert clamp(1, 0, 2) == 1\n"}
    user, assistant = t2_messages(example)

    assert user["content"].startswith("Write pytest unit tests for the function `clamp` below.")
    assert assistant["content"] == "```python\n" + example["tests"] + "```"
