"""Mixing the fine-tuning data: group-level splits, T1/T3 reservation, explanation choice.

Groups are seed problems (e.g. "KAKA22/CodeRM-UnitTest:8593"). Every example derived from one
group lands in the same split, so a problem never appears on both sides of train/test. Hashes
use SHA-256 (Python's hash() is salted per process and would not be reproducible).
"""

import hashlib

from training.data.format import template_explanation
from training.data.teacher import accept_explanation


def _bucket(salt: str, group: str, modulo: int) -> int:
    return int(hashlib.sha256(f"{salt}:{group}".encode()).hexdigest(), 16) % modulo


def assign_split(group: str) -> str:
    """90 % train, 5 % validation, 5 % internal test, by group."""
    b = _bucket("split", group, 100)
    return "train" if b < 90 else "val" if b < 95 else "test"


def reserved_for_t3(group: str) -> bool:
    """A quarter of the T1 pool's groups become T3 review pairs instead of T1 repair examples."""
    return _bucket("t3", group, 4) == 0


def explanation_for(example: dict, teacher_text: str | None) -> tuple[str, str]:
    """(explanation, origin): the teacher's text if accepted, otherwise the template."""
    if teacher_text and accept_explanation(example, teacher_text):
        return teacher_text.strip(), "teacher"
    return template_explanation(example), "template"
