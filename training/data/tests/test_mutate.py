import ast
import difflib

from training.data.mutate import enumerate_mutants

SOURCE = '''def count_close(values, limit):
    # count pairs closer than limit
    total = 0
    for i in range(1, len(values)):
        if values[i] - values[i - 1] < limit and values[i] > 0:
            total += 1
    return total
'''


def changed_lines(a: str, b: str) -> list[str]:
    return [l for l in difflib.unified_diff(a.splitlines(), b.splitlines(), lineterm="", n=0)
            if l.startswith(("+", "-")) and not l.startswith(("+++", "---"))]


def test_every_mutant_parses_and_changes_exactly_one_line():
    mutants = enumerate_mutants(SOURCE)

    assert mutants
    for m in mutants:
        ast.parse(m.code)
        diff = changed_lines(SOURCE, m.code)
        assert len(diff) == 2, (m.operator, diff)  # one line removed, one added


def test_comments_and_untouched_lines_are_preserved():
    for m in enumerate_mutants(SOURCE):
        assert "# count pairs closer than limit" in m.code


def test_comparison_flip():
    codes = [m.code for m in enumerate_mutants(SOURCE) if m.operator == "comparison_flip"]
    assert any("values[i] - values[i - 1] <= limit" in c for c in codes)
    assert any("values[i] >= 0" in c for c in codes)


def test_boolean_swap():
    codes = [m.code for m in enumerate_mutants(SOURCE) if m.operator == "boolean_swap"]
    assert any(" or values[i] > 0" in c for c in codes)


def test_off_by_one_on_integer_constants():
    codes = [m.code for m in enumerate_mutants(SOURCE) if m.operator == "off_by_one"]
    assert any("range(2, len(values))" in c for c in codes)
    assert any("values[i - 2]" in c for c in codes)


def test_arithmetic_swap():
    codes = [m.code for m in enumerate_mutants(SOURCE) if m.operator == "arithmetic_swap"]
    assert any("values[i] + values[i - 1]" in c for c in codes)
    assert any("total -= 1" in c for c in codes)


def test_negate_condition():
    codes = [m.code for m in enumerate_mutants(SOURCE) if m.operator == "negate_condition"]
    assert any("if not (values[i] - values[i - 1] < limit and values[i] > 0):" in c for c in codes)


def test_mutants_record_line_and_are_deterministic():
    first, second = enumerate_mutants(SOURCE), enumerate_mutants(SOURCE)
    assert [(m.operator, m.line, m.code) for m in first] == [(m.operator, m.line, m.code) for m in second]
    assert all(1 <= m.line <= SOURCE.count("\n") for m in first)


def test_non_ascii_source_is_spliced_correctly():
    src = 'def f(s):\n    # é ü\n    return s == "é" and len(s) < 2\n'
    for m in enumerate_mutants(src):
        ast.parse(m.code)
        assert '"é"' in m.code
