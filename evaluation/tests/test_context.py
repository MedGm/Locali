import ast
import json
from pathlib import Path

import pytest

from evaluation.tasks.context import compress_python, parse_repair_prompt
from training.data.format import repair_prompt

MIX = Path(__file__).resolve().parents[2] / "data" / "mix_v2" / "test.jsonl"


@pytest.mark.skipif(not MIX.exists(), reason="mixture not built")
def test_parse_and_rebuild_reproduces_every_t1_prompt():
    rows = [json.loads(line) for line in MIX.read_text().splitlines()]
    prompts = [r["messages"][0]["content"] for r in rows if r["task"] == "T1"]
    assert len(prompts) == 212
    for p in prompts:
        assert repair_prompt(**parse_repair_prompt(p)) == p


def test_compress_drops_comments_docstrings_and_blank_lines():
    src = '''def area(r):
    """Area of a circle.

    r: radius
    """
    # pi is approximate
    pi = 3.14  # good enough

    return pi * r * r  # done
'''
    out = compress_python(src)
    assert out == "def area(r):\n    pi = 3.14\n    return pi * r * r"
    ast.parse(out)


def test_compress_keeps_strings_with_hashes_and_a_lone_docstring():
    src = 'def f():\n    """Only a docstring."""\n\n\ndef g():\n    return "#notacomment"\n'
    out = compress_python(src)
    assert '"#notacomment"' in out
    assert '"""Only a docstring."""' in out
    ast.parse(out)


def test_compress_handles_an_indented_test_method_snippet():
    snippet = "def test_x(self):\n        # check\n        self.assertEqual(f(1), 2)  # one\n"
    assert compress_python(snippet) == "def test_x(self):\n        self.assertEqual(f(1), 2)"
