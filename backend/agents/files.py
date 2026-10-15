"""Which files of a repository count as code and which as tests."""

from pathlib import Path

SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules"}


def is_test_file(rel: Path) -> bool:
    return "tests" in rel.parts or rel.name.startswith("test_") or rel.name == "conftest.py"


def python_files(root: Path) -> list[Path]:
    return [p for p in sorted(root.rglob("*.py")) if not SKIP_DIRS & set(p.relative_to(root).parts)]
