import json

from training.data.format import parse_repair_answer
from training.data.v3_repair import bug_function, first_changed_line, v3_messages

FIXED = "def helper(x):\n    return x * 2\n\ndef total(xs):\n    s = 0\n    for x in xs:\n        s += helper(x)\n    return s\n"
BUGGY = FIXED.replace("        s += helper(x)\n", "        s = helper(x)\n")
BUG = {"source": "KAKA22/CodeRM-UnitTest:1", "kind": "wrong_update", "buggy_code": BUGGY, "fixed_code": FIXED,
       "description": "The loop assigns instead of adding, so only the last element counts. Extra words here.",
       "error": "AssertionError: 6 != 12", "tests": "import unittest\nclass T(unittest.TestCase):\n    pass\n"}


def test_the_first_changed_line_is_found_in_the_buggy_code():
    assert first_changed_line(FIXED, BUGGY) == "        s = helper(x)"


def test_the_function_holding_the_bug_is_named():
    assert bug_function(BUGGY, FIXED) == "total"


def test_repair_format_gives_error_and_answers_with_diagnosis_and_whole_function():
    user, assistant = v3_messages(BUG, "repair")
    assert "AssertionError: 6 != 12" in user["content"] and BUGGY.strip() in user["content"]
    diagnosis, code = parse_repair_answer(assistant["content"])
    assert diagnosis["bug_location"] == "        s = helper(x)"
    assert diagnosis["explanation"] == "The loop assigns instead of adding, so only the last element counts."
    assert code.strip() == FIXED.strip()


def test_benchmark_format_names_the_function_and_answers_with_code_only():
    user, assistant = v3_messages(BUG, "benchmark")
    assert user["content"].startswith("Fix bugs in total.")
    assert "These tests fail:" in user["content"]
    assert assistant["content"] == f"```python\n{FIXED.rstrip()}\n```"
    json.dumps([user, assistant])
