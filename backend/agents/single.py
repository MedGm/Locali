"""Single-agent baseline for the ablation: one model call per file, no tools, tests or sandbox.

The model reviews each whole file in the same T3 format the multi-step workflow uses per
function, so the comparison is about splitting the work and adding tools, not about the format.
"""

from pathlib import Path

from backend.agents.files import is_test_file, python_files
from backend.agents.review import Model, ReviewResult, review_span


def review_files(root: str | Path, model: Model, files: list[str] | None = None) -> ReviewResult:
    root = Path(root)
    if files is None:
        files = [p.relative_to(root).as_posix() for p in python_files(root) if not is_test_file(p.relative_to(root))]
    result = ReviewResult()
    for rel in files:
        lines = (root / rel).read_text().splitlines()
        if lines:
            review_span(model, rel, lines, 1, result)
    return result
