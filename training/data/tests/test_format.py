import json

from training.data.format import parse_repair_answer, t1_messages, template_explanation

EXAMPLE = {
    "bug_type": "wrong comparison operator",
    "line": 4,
    "original_snippet": "x > hi",
    "mutated_snippet": "x >= hi",
    "buggy_code": "def clamp(x, lo, hi):\n    if x < lo:\n        return lo\n    if x >= hi:\n        return hi\n    return x\n",
    "fixed_code": "def clamp(x, lo, hi):\n    if x < lo:\n        return lo\n    if x > hi:\n        return hi\n    return x\n",
    "failing_test": {"name": "TestClamp::test_edges", "code": "def test_edges(self):\n    self.assertEqual(clamp(10, 0, 10), 10)",
                     "error": "AssertionError: 10 != 9"},
}


def test_user_prompt_shows_bug_context_but_not_the_fix():
    user = t1_messages(EXAMPLE, "why")[0]

    assert user["role"] == "user"
    assert "if x >= hi:" in user["content"]
    assert "def test_edges(self):" in user["content"]
    assert "AssertionError: 10 != 9" in user["content"]
    assert "if x > hi:" not in user["content"]


def test_assistant_answer_is_json_diagnosis_then_fixed_code():
    assistant = t1_messages(EXAMPLE, "The comparison is off.")[1]
    diagnosis, code = parse_repair_answer(assistant["content"])

    assert assistant["role"] == "assistant"
    assert diagnosis == {"bug_location": "    if x >= hi:", "bug_type": "wrong comparison operator",
                         "explanation": "The comparison is off."}
    assert code == EXAMPLE["fixed_code"].rstrip("\n")


def test_template_explanation_names_location_and_fix():
    text = template_explanation(EXAMPLE)
    assert "x >= hi" in text and "x > hi" in text and "test_edges" in text


def test_parse_repair_answer_tolerates_missing_diagnosis():
    diagnosis, code = parse_repair_answer("```python\ndef f():\n    return 1\n```")
    assert diagnosis is None
    assert code == "def f():\n    return 1"


def test_diagnosis_is_valid_single_line_json():
    first_line = t1_messages(EXAMPLE, 'quote " and newline\n inside')[1]["content"].splitlines()[0]
    assert json.loads(first_line)["explanation"] == 'quote " and newline\n inside'


def test_parse_repair_answer_handles_braces_inside_the_explanation():
    text = json.dumps({"bug_location": "    d = {1: 'a'}", "bug_type": "t", "explanation": "uses {1: 'a'} not {1: 'b'}"}) + "\n```python\nx = 1\n```"
    diagnosis, code = parse_repair_answer(text)
    assert diagnosis["explanation"] == "uses {1: 'a'} not {1: 'b'}"
    assert code == "x = 1"
