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


V2_SOURCE = '''def stats(values, limit):
    total = 0
    best = max(values)
    for v in values:
        if v > 0 and v < limit:
            total = total + abs(v)
    name = "x".upper()
    return total, best, name
'''


def _v2(operator: str) -> set[str]:
    return {m.replacement for m in enumerate_mutants(V2_SOURCE, family="v2") if m.operator == operator}


def test_v1_family_is_unchanged_by_default():
    assert {m.operator for m in enumerate_mutants(V2_SOURCE)} <= {
        "comparison_flip", "boolean_swap", "arithmetic_swap", "off_by_one", "negate_condition"}
    assert enumerate_mutants(V2_SOURCE) == enumerate_mutants(V2_SOURCE, family="v1")


def test_v2_mutants_parse_and_change_exactly_one_line():
    mutants = enumerate_mutants(V2_SOURCE, family="v2")
    assert {m.operator for m in mutants} == {"variable_misuse", "missing_condition", "missing_term",
                                               "missing_call", "function_swap"}
    for m in mutants:
        ast.parse(m.code)
        changed = [d for d in difflib.ndiff(V2_SOURCE.splitlines(), m.code.splitlines()) if d.startswith("+ ")]
        assert len(changed) == 1


def test_function_swap_and_missing_call():
    assert "min" in _v2("function_swap") and "lower" in _v2("function_swap")
    assert "v" in _v2("missing_call")


def test_missing_condition_and_missing_term():
    assert {"v > 0", "v < limit"} <= _v2("missing_condition")
    assert "total" in _v2("missing_term") or "abs(v)" in _v2("missing_term")


def test_variable_misuse_uses_other_local_names_only():
    replacements = _v2("variable_misuse")
    assert replacements and replacements <= {"values", "limit", "total", "best", "v", "name"}
