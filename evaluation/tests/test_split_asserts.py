import ast

from evaluation.tasks.testgen import split_asserts

TEST_FN = '''import pytest
from solution import f


def test_many():
    x = 1
    assert f(x) == 1
    y = 2
    assert f(y) == 2, "second"


def helper():
    assert True
'''


def test_splits_each_top_level_assert_into_its_own_test_with_preceding_setup():
    tree = ast.parse(split_asserts(TEST_FN))
    tests = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")}

    assert sorted(tests) == ["test_many__a0", "test_many__a1"]
    second = ast.unparse(tests["test_many__a1"])
    assert "x = 1" in second and "y = 2" in second
    assert "assert f(x) == 1" not in second
    assert "assert f(y) == 2, 'second'" in second


def test_leaves_non_test_functions_and_imports_alone():
    out = split_asserts(TEST_FN)
    assert "def helper():" in out and "import pytest" in out


def test_keeps_decorators_and_class_methods():
    code = '''import pytest

@pytest.mark.parametrize("v", [1, 2])
def test_p(v):
    assert v > 0
    assert v < 3


class TestK:
    def test_m(self):
        assert 1
        assert 2
'''
    out = split_asserts(code)
    tree = ast.parse(out)
    names = sorted(n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    assert names == ["test_m__a0", "test_m__a1", "test_p__a0", "test_p__a1"]
    assert out.count("@pytest.mark.parametrize") == 2


def test_function_with_single_assert_or_nested_asserts_is_unchanged():
    code = "def test_one():\n    assert 1\n\n\ndef test_loop():\n    for i in range(3):\n        assert i < 3\n"
    assert split_asserts(code) == code


def test_unparseable_code_is_returned_unchanged():
    assert split_asserts("def test_(:\n") == "def test_(:\n"
