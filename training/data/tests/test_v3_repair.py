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


def test_diagnosis_prompt_gives_both_versions_and_asks_for_the_reviewer_view():
    from training.data.v3_repair import diagnosis_messages

    text = diagnosis_messages(BUGGY, FIXED, BUG["description"], "wrong_update")[-1]["content"]
    assert BUGGY.strip() in text and FIXED.strip() in text and "reviewer" in text


def test_a_reviewer_diagnosis_is_accepted():
    from training.data.v3_repair import accept_diagnosis

    good = "The loop assigns `s = helper(x)` instead of adding to `s`, so only the last element is counted."
    assert accept_diagnosis(good, "        s = helper(x)") == good


def test_bug_maker_wording_cut_sentences_and_unrelated_text_are_rejected():
    from training.data.v3_repair import accept_diagnosis

    line = "        s = helper(x)"
    assert accept_diagnosis("Changed `s += helper(x)` to `s = helper(x)`.", line) is None
    assert accept_diagnosis("The loop assigns `s = helper(x)` instead of adding to it, so only the la", line) is None
    assert accept_diagnosis("The function has a logic error in its main loop.", line) is None


def test_template_names_the_line_when_no_diagnosis_is_accepted():
    from training.data.v3_repair import template_diagnosis

    text = template_diagnosis("        s = helper(x)", "wrong_update")
    assert "`s = helper(x)`" in text and text.endswith(".")


def test_one_letter_names_in_backticks_count_as_naming_the_bug():
    from training.data.v3_repair import accept_diagnosis

    text = "The batch count divides `n` by `m` instead of `m + 1`, so the free item is counted too often."
    assert accept_diagnosis(text, "        f = n // m * m") == text
    assert accept_diagnosis("It is a mistake in a loop.", "        f = n // m * m") is None
