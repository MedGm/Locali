"""Secret detection and redaction for text sent to or produced by the model.

Known token formats are matched first; a generic rule then catches assignments such as
`API_KEY = "..."` when the value looks random (Shannon entropy check). Redaction replaces
only the value, so redacted code still parses.
"""

import math
import re
from collections import Counter
from dataclasses import dataclass

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


def redact(text: str) -> str:
    for f in sorted(scan_text(text), key=lambda f: f.start, reverse=True):
        text = text[: f.start] + f"[REDACTED:{f.rule}]" + text[f.end :]
    return text
