"""Which files of a repository count as code and which as tests."""

import os
from pathlib import Path

SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules"}


def is_test_file(rel: Path) -> bool:
    return "tests" in rel.parts or rel.name.startswith("test_") or rel.name == "conftest.py"


def python_files(root: Path) -> list[Path]:
    found = []
    for folder, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]  # prune instead of walking node_modules and filtering
        found += [Path(folder) / f for f in files if f.endswith(".py")]
    return sorted(found)
