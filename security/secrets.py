"""Secret detection and redaction for text sent to or produced by the model.

Known token formats are matched first; a generic rule then catches assignments such as
`API_KEY = "..."` when the value looks random (Shannon entropy check). Redaction replaces
only the value, so redacted code still parses.

The generic rule needs the assignment around the value, so a value repeated on its own (a model
answer saying "the key is ...") would pass. secret_values() collects the values found in a
repository, and redact(text, known) also removes those exact strings wherever they appear.
"""

import math
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

PATTERNS = [
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----")),
    ("aws-access-key", re.compile(r"(?<![A-Z0-9])(?:AKIA|ASIA)[0-9A-Z]{16}(?![A-Z0-9])")),
    ("aws-secret-key", re.compile(r"(?i)aws_secret_access_key\s*[:=]\s*[\"']?(?P<value>[A-Za-z0-9/+=]{40})")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}")),
    ("huggingface-token", re.compile(r"\bhf_[A-Za-z0-9]{30,}")),
    ("slack-token", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}")),
    ("generic-secret", re.compile(
        r"(?i)\b\w*(?:secret|token|passw(?:or)?d|api_?key)(?:_\w*)?\s*[:=]\s*[\"'](?P<value>[^\"'\s]{12,})[\"']")),
]
MIN_ENTROPY = 3.0


@dataclass(frozen=True)
class SecretFinding:
    rule: str
    line: int
    start: int
    end: int


def _entropy(s: str) -> float:
    counts = Counter(s)
    return -sum(c / len(s) * math.log2(c / len(s)) for c in counts.values())


def scan_text(text: str) -> list[SecretFinding]:
    found: list[SecretFinding] = []
    taken: list[tuple[int, int]] = []
    for rule, pattern in PATTERNS:
        for m in pattern.finditer(text):
            group = "value" if "value" in pattern.groupindex else 0
            start, end = m.span(group)
            value = m.group(group)
            if rule == "generic-secret" and ("://" in value or _entropy(value) < MIN_ENTROPY):
                continue
            if any(start < e and s < end for s, e in taken):
                continue  # a more specific rule already covers it
            taken.append((start, end))
            found.append(SecretFinding(rule, text.count("\n", 0, start) + 1, start, end))
    return sorted(found, key=lambda f: f.start)


def redact(text: str, known: Iterable[str] = ()) -> str:
    for f in sorted(scan_text(text), key=lambda f: f.start, reverse=True):
        text = text[: f.start] + f"[REDACTED:{f.rule}]" + text[f.end :]
    for value in sorted(known, key=len, reverse=True):
        text = text.replace(value, "[REDACTED:known-secret]")
    return text


SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules"}
MAX_FILE_BYTES = 1_000_000


def secret_values(root: str | Path) -> set[str]:
    """Every secret value the scanner finds in the text files of a repository."""
    root = Path(root)
    values = set()
    for path in root.rglob("*"):
        if not path.is_file() or SKIP_DIRS & set(path.relative_to(root).parts) or path.stat().st_size > MAX_FILE_BYTES:
            continue
        try:
            text = path.read_text()
        except (UnicodeDecodeError, OSError):
            continue
        values |= {text[f.start:f.end] for f in scan_text(text) if f.end - f.start >= 8}
    return values
