from backend.agents.docs import (
    docstring_only_change,
    generate_docs,
    insert_docstring,
    undocumented_functions,
)

SOURCE = '''import os


def area(w, h):
    return w * h


@staticmethod
def scaled(x,
           factor=2):
    """Already documented."""
    return x * factor


def _private(x):
    return x


def one_liner(x): return x


class Box:
    def volume(self, d):
        return d
'''


def test_finds_public_functions_and_methods_without_docstrings(tmp_path):
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "geo.py").write_text(SOURCE)
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_geo.py").write_text("def test_x():\n    pass\n")
    assert undocumented_functions(tmp_path) == [("pkg/geo.py", "area"), ("pkg/geo.py", "Box.volume")]


def test_insert_docstring_keeps_everything_else():
    new = insert_docstring(SOURCE, "area", "Return the area of a w by h rectangle.")
    assert '    """Return the area of a w by h rectangle."""\n    return w * h' in new
    new = insert_docstring(new, "Box.volume", "Volume.")
    assert '        """Volume."""\n        return d' in new
    assert docstring_only_change(SOURCE, new)


def test_insert_docstring_neutralises_quotes_and_backslashes():
    new = insert_docstring(SOURCE, "area", 'Area """ then code\\n')
    assert docstring_only_change(SOURCE, new)
    assert '"""' not in new.split("def area")[1].splitlines()[1].strip().strip('"')


def test_docstring_only_change_rejects_code_changes():
    assert not docstring_only_change(SOURCE, SOURCE.replace("w * h", "w + h"))
    assert not docstring_only_change(SOURCE, SOURCE + "\nx = 1\n")
    assert not docstring_only_change(SOURCE, "def broken(:\n")


def fake_model(messages):
    prompt = messages[-1]["content"]
    assert prompt.startswith("Write a one-line docstring")
    if "def area" in prompt:
        return "```python\n\"\"\"Return the area of a w by h rectangle.\"\"\"\n```"
    return "Return d."


def test_generate_docs_writes_docstrings_and_respects_the_skip_list(tmp_path):
    (tmp_path / "geo.py").write_text(SOURCE)
    (tmp_path / "other.py").write_text("def f():\n    return 1\n")
    result = generate_docs(tmp_path, fake_model, skip={("other.py", "f")})
    assert result.files == ["geo.py"]
    assert result.documented == [("geo.py", "area"), ("geo.py", "Box.volume")]
    text = (tmp_path / "geo.py").read_text()
    assert '"""Return the area of a w by h rectangle."""' in text and '"""Return d."""' in text
    assert (tmp_path / "other.py").read_text() == "def f():\n    return 1\n"


def test_generate_docs_stops_at_the_limit(tmp_path):
    (tmp_path / "geo.py").write_text(SOURCE)
    result = generate_docs(tmp_path, fake_model, limit=1)
    assert result.documented == [("geo.py", "area")]
