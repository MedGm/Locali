import json

import pytest

from backend.agents.context import CONTEXTS, function_context
from backend.agents.review import review_functions

SOURCE = '''import math

RATE = 0.2
UNUSED = 5


def helper(x):
    return x * RATE


def area(r):
    """Area of a circle, rounded."""
    # pi from math
    value = math.pi * r * r

    return round(helper(value), 2)  # keep 2 digits


def other():
    return UNUSED
'''


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "geo.py").write_text(SOURCE)
    return tmp_path


def test_function_context_is_the_function_alone(repo):
    text = function_context(repo, "geo.py", "area", "function")
    assert text.startswith("def area(r):") and "def helper" not in text and "RATE" not in text


def test_slice_adds_what_the_function_uses_and_nothing_else(repo):
    text = function_context(repo, "geo.py", "area", "slice")
    assert "def area(r):" in text and "def helper" in text and "RATE = 0.2" in text and "import math" in text
    assert "UNUSED" not in text and "def other" not in text


def test_compact_drops_docstring_comment_lines_and_blank_lines(repo):
    text = function_context(repo, "geo.py", "area", "compact")
    assert text.splitlines() == ["def area(r):", "    value = math.pi * r * r",
                                 "    return round(helper(value), 2)  # keep 2 digits"]


def test_file_context_is_the_whole_file(repo):
    assert function_context(repo, "geo.py", "area", "file") == SOURCE


def recording(answer):
    prompts = []

    def model(messages):
        prompts.append(messages[-1]["content"])
        return answer
    return model, prompts


@pytest.mark.parametrize("context", CONTEXTS)
def test_review_findings_are_located_in_the_target_function_whatever_the_context(repo, context):
    answer = json.dumps({"findings": [
        {"line": "    return round(helper(value), 2)  # keep 2 digits", "category": "bug", "severity": "low", "message": "m"},
        {"line": "    return UNUSED", "category": "bug", "severity": "low", "message": "elsewhere"},
    ]})
    model, prompts = recording(answer)
    result = review_functions(repo, model, [("geo.py", "area")], context=context)
    assert [(f["path"], f["line"]) for f in result.findings] == [("geo.py", 16)]
    assert len(prompts) == 1


def test_file_context_reviews_each_file_once(repo):
    model, prompts = recording(json.dumps({"findings": [{"line": "    return UNUSED", "category": "quality",
                                                          "severity": "low", "message": "m"}]}))
    result = review_functions(repo, model, None, context="file")
    assert len(prompts) == 1 and [(f["line"]) for f in result.findings] == [20]


@pytest.mark.parametrize(("context", "has_rate"), [("function", False), ("slice", True), ("file", True)])
def test_testgen_prompt_follows_the_context(repo, context, has_rate, monkeypatch):
    from backend.agents import testgen

    monkeypatch.setattr(testgen, "run_tests", lambda *a, **k: {"failed": [], "errors": 0, "timed_out": False})
    model, prompts = recording("```python\nfrom solution import area\n\n\ndef test_area():\n    assert area(0) == 0\n```")
    testgen.generate_tests(repo, model, [("geo.py", "area")], context=context)
    assert ("RATE = 0.2" in prompts[0]) is has_rate and "def area(r):" in prompts[0]
