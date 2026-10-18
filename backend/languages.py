"""Which languages a repository is written in, by file extension.

Quick scans cover all of these (Semgrep rules, secret scan, injection detector). The full assistant
needs Python: its tests, repair loop and patch validation rely on pytest and Python's parser.
"""

from collections import Counter
from pathlib import Path

from backend.agents.files import SKIP_DIRS

EXTENSIONS = {
    ".py": "python",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
}
SKIP = SKIP_DIRS | {"dist", "build", ".next", "target", "vendor"}


def count_languages(root: str | Path) -> dict[str, int]:
    root = Path(root)
    counts: Counter = Counter()
    for path in root.rglob("*"):
        language = EXTENSIONS.get(path.suffix.lower())
        if language and path.is_file() and not SKIP & set(path.relative_to(root).parts):
            counts[language] += 1
    return dict(counts.most_common())
