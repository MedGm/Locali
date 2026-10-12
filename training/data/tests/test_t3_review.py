import json

from training.data.t3_review import (
    parse_review_answer,
    t3_items_from_bug_pair,
    t3_messages,
    tool_findings,
)

UNSAFE = "import os\nimport subprocess\n\n\ndef run(cmd, items=[]):\n    unused = 1\n    return subprocess.call(cmd, shell=True)\n"
BUG_EXAMPLE = {
    "id": "t1-7-0", "source": "KAKA22/CodeRM-UnitTest:7", "bug_type": "wrong comparison operator", "line": 2,
    "original_snippet": "x > 0", "mutated_snippet": "x >= 0",
    "buggy_code": "def pos(x):\n    return x >= 0\n", "fixed_code": "def pos(x):\n    return x > 0\n",
    "failing_test": {"name": "T::test_zero", "code": "", "error": "AssertionError: True is not false"},
}


def test_tool_findings_report_security_and_quality_with_verbatim_lines():
    findings = tool_findings(UNSAFE)
    by_category = {f["category"] for f in findings}

    assert by_category == {"security", "quality"}
    shell = next(f for f in findings if f["category"] == "security" and "shell" in f["message"].lower())
    assert shell["line"] == "    return subprocess.call(cmd, shell=True)"
    assert shell["severity"] == "high"
    assert any("os" in f["message"] and f["line"] == "import os" for f in findings)  # unused import
    assert any(f["line"] == "def run(cmd, items=[]):" for f in findings)  # mutable default (bugbear)


def test_clean_code_has_no_findings():
    assert tool_findings("def add(a, b):\n    return a + b\n") == []


def test_bug_pair_gives_a_buggy_item_with_a_bug_finding_and_a_clean_item_without():
    buggy, clean = t3_items_from_bug_pair(BUG_EXAMPLE, message="`x >= 0` treats 0 as positive.")

    assert buggy["code"] == BUG_EXAMPLE["buggy_code"]
    assert buggy["findings"] == [{"line": "    return x >= 0", "category": "bug", "severity": "high",
                                  "message": "`x >= 0` treats 0 as positive."}]
    assert clean["code"] == BUG_EXAMPLE["fixed_code"]
    assert clean["findings"] == []
    assert buggy["group"] == clean["group"] == "KAKA22/CodeRM-UnitTest:7"


def test_messages_answer_is_parseable_json_and_empty_list_is_allowed():
    _, clean = t3_items_from_bug_pair(BUG_EXAMPLE, message="m")
    user, assistant = t3_messages(clean)

    assert "def pos(x):" in user["content"]
    assert json.loads(assistant["content"]) == {"findings": []}
    assert parse_review_answer(assistant["content"]) == []


def test_parse_review_answer_handles_fenced_json_and_garbage():
    assert parse_review_answer('```json\n{"findings": [{"line": "x", "category": "bug", "severity": "high", "message": "m"}]}\n```')[0]["line"] == "x"
    assert parse_review_answer("no json here") is None
