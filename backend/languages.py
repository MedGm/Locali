"""Which languages a repository is written in, by file extension.

Quick scans cover all of these (Semgrep rules, secret scan, injection detector). The full assistant
needs Python: its tests, repair loop and patch validation rely on pytest and Python's parser.
"""

import os
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
    counts: Counter = Counter()
    for _, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP]  # never descend into node_modules and the like
        for name in files:
            language = EXTENSIONS.get(os.path.splitext(name)[1].lower())
            if language:
                counts[language] += 1
    return dict(counts.most_common())
