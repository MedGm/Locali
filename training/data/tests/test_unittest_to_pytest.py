import ast

from training.data.t2_tests import unittest_to_pytest

SUITE = '''import unittest

class TestClamp(unittest.TestCase):
    def test_inside(self):
        # a value in range is returned as is
        self.assertEqual(clamp(5, 0, 10), 5)

    def test_flags(self):
        self.assertTrue(is_ok(1))
        self.assertFalse(is_ok(-1))
        self.assertIsNone(find([], 1))
        self.assertIn(3, items())
        self.assertNotEqual(clamp(1, 0, 10), 0)
        self.assertGreater(clamp(11, 0, 10), 9)
        self.assertAlmostEqual(ratio(1, 3), 0.3333, places=3)

    def test_raises(self):
        with self.assertRaises(ValueError):
            clamp(1, 10, 0)
        self.assertRaises(TypeError, clamp, "a", 0, 1)

if __name__ == "__main__":
    unittest.main()
'''


def test_converts_methods_to_functions_with_plain_asserts():
    out = unittest_to_pytest(SUITE, entry_point="clamp")
    tree = ast.parse(out)
    names = [n.name for n in tree.body if isinstance(n, ast.FunctionDef)]

    assert names == ["test_inside", "test_flags", "test_raises"]
    assert "from solution import *" in out
    assert "assert clamp(5, 0, 10) == 5" in out
    assert "assert is_ok(1)" in out and "assert not is_ok(-1)" in out
    assert "assert find([], 1) is None" in out
    assert "assert 3 in items()" in out
    assert "assert clamp(1, 0, 10) != 0" in out
    assert "assert clamp(11, 0, 10) > 9" in out
    assert "assert ratio(1, 3) == pytest.approx(0.3333, abs=0.001)" in out
    assert "with pytest.raises(ValueError):" in out
    assert "with pytest.raises(TypeError):\n        clamp('a', 0, 1)" in out
    assert "self" not in out and "unittest" not in out


def test_returns_none_for_unsupported_suites():
    with_setup = SUITE.replace("    def test_inside(self):", "    def setUp(self):\n        self.x = 1\n\n    def test_inside(self):")
    assert unittest_to_pytest(with_setup, entry_point="clamp") is None
    unknown = SUITE.replace("self.assertTrue(is_ok(1))", "self.assertRegex(name(), 'a+')")
    assert unittest_to_pytest(unknown, entry_point="clamp") is None
    assert unittest_to_pytest("def broken(:", entry_point="clamp") is None


def test_class_docstring_is_allowed():
    suite = SUITE.replace("class TestClamp(unittest.TestCase):\n", 'class TestClamp(unittest.TestCase):\n    """Tests for clamp."""\n\n')
    assert unittest_to_pytest(suite, entry_point="clamp") is not None
