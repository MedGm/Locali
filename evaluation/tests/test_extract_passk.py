import pytest

from evaluation.extract import extract_code
from evaluation.passk import pass_at_k


def test_extracts_python_fenced_block():
    text = "Here you go:\n```python\ndef f():\n    return 1\n```\nDone."
    assert extract_code(text) == "def f():\n    return 1"


def test_prefers_block_defining_entry_point():
    text = "```python\nimport math\n```\nThen:\n```python\ndef area(r):\n    return math.pi * r * r\n```"
    assert extract_code(text, entry_point="area") == "def area(r):\n    return math.pi * r * r"


def test_extracts_unlabelled_fence():
    assert extract_code("```\nx = 1\n```") == "x = 1"


def test_returns_raw_text_without_fence():
    assert extract_code("def f():\n    return 2\n") == "def f():\n    return 2"


def test_strips_thinking_block():
    text = "<think>\nlet me think\n```python\nwrong()\n```\n</think>\n```python\nright()\n```"
    assert extract_code(text) == "right()"


def test_pass_at_1_equals_success_ratio():
    assert pass_at_k(n=10, c=3, k=1) == pytest.approx(0.3)


def test_pass_at_k_is_one_when_failures_fewer_than_k():
    assert pass_at_k(n=10, c=8, k=5) == 1.0


def test_pass_at_k_matches_unbiased_estimator():
    # 1 - C(n-c, k) / C(n, k) with n=10, c=2, k=3: 1 - 56/120
    assert pass_at_k(n=10, c=2, k=3) == pytest.approx(1 - 56 / 120)
