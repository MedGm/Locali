from evaluation.tests.test_codegen import needs_docker
from training.data.t1_bugs import Seed
from training.data.t4_trace import call_cases, parse_trace_answer, t4_messages, trace_seed

CODE = "def scale(arr, k):\n    return [x * k for x in arr]\n\ndef helper(x):\n    return x\n"
TESTS = """import unittest

class TestScale(unittest.TestCase):
    def test_basic(self):
        arr = [1, 2, 3]
        k = 2
        self.assertEqual(scale(arr, k), [2, 4, 6])

    def test_expression_expected(self):
        arr = [1]
        self.assertEqual(scale(arr, 3), sum([3]))

    def test_non_literal_input(self):
        arr = list(range(3))
        self.assertEqual(scale(arr, 1), [0, 1, 2])

    def test_arrange_act_assert(self):
        values = [4]
        expected_output = [8]
        result = scale(values, 2)
        self.assertEqual(result, expected_output)

    def test_wrong_expected(self):
        self.assertEqual(scale([5], 2), [11])
"""


def test_call_cases_inline_literal_assignments_and_skip_the_rest():
    cases = call_cases(CODE, TESTS)
    assert ("scale([1, 2, 3], 2)", "[2, 4, 6]") in cases
    assert ("scale([5], 2)", "[11]") in cases
    assert ("scale([4], 2)", "[8]") in cases
    assert all("range" not in call and "sum" not in expected for call, expected in cases)


@needs_docker
def test_trace_seed_keeps_only_calls_whose_traced_value_matches_the_test():
    examples = trace_seed(Seed("7", "q", CODE, TESTS), max_calls=5)
    assert [ex["call"] for ex in examples] == ["scale([1, 2, 3], 2)", "scale([4], 2)"]
    assert examples[0]["output"] == "[2, 4, 6]"
    assert examples[0]["source"] == "KAKA22/CodeRM-UnitTest:7"


def test_t4_messages_and_answer_parser_round_trip():
    ex = {"code": CODE, "call": "scale([1, 2, 3], 2)", "output": "[2, 4, 6]"}
    messages = t4_messages(ex)
    assert "scale([1, 2, 3], 2)" in messages[0]["content"] and "[ANSWER]" not in messages[0]["content"]
    assert messages[1]["content"] == "assert scale([1, 2, 3], 2) == [2, 4, 6]"
    assert parse_trace_answer(messages[1]["content"]) == "[2, 4, 6]"
    assert parse_trace_answer("```python\nassert scale([1], 2) == [2]\n```") == "[2]"
