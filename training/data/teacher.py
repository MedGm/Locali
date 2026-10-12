"""Teacher (Qwen3.5-9B) explanations for T1/T3 bug examples, and their acceptance check.

The teacher only phrases why a known, test-verified fault is wrong; it never decides labels.
An explanation is accepted if it is 20-400 characters, refers to the buggy or the correct code,
and does not reveal how the example was built. Rejected ones fall back to the template.
"""

import re

_LEAKS = re.compile(r"mutat|inject|synthetic|artificial", re.IGNORECASE)


def teacher_messages(example: dict) -> list[dict]:
    test = example["failing_test"]
    content = (
        "You are reviewing a Python function that fails a unit test because of one wrong line.\n\n"
        f"```python\n{example['buggy_code'].rstrip()}\n```\n\n"
        f"Wrong code: `{example['mutated_snippet']}` (line {example['line']}). "
        f"Correct code: `{example['original_snippet']}`.\n"
        f"Failing test `{test['name']}`:\n```python\n{test['code'].rstrip()}\n```\n"
        f"Error: {test['error'].strip()}\n\n"
        "In one or two sentences, explain to the author why the wrong code is a bug and what the "
        "correct behaviour is, as a code reviewer would. Refer to the code directly. "
        "Answer with the explanation only."
    )
    return [{"role": "user", "content": content}]


def _squash(text: str) -> str:
    return re.sub(r"[\s`]+", "", text)


MIN_CHARS, MAX_CHARS = 20, 400


def accept_explanation(example: dict, text: str) -> bool:
    text = text.strip()
    if not MIN_CHARS <= len(text) <= MAX_CHARS or _LEAKS.search(text):
        return False
    flat = _squash(text)
    return _squash(example["mutated_snippet"]) in flat or _squash(example["original_snippet"]) in flat


def _sentences(text: str) -> list[str]:
    """Split at . ! ? followed by whitespace or the end, ignoring punctuation inside `code`."""
    out, start, in_code = [], 0, False
    for i, ch in enumerate(text):
        if ch == "`":
            in_code = not in_code
        elif ch in ".!?" and not in_code and (i + 1 == len(text) or text[i + 1].isspace()):
            out.append(text[start : i + 1].strip())
            start = i + 1
    rest = text[start:].strip()
    return [s for s in [*out, rest] if s]


def condense(text: str, cut: bool) -> str:
    """Shorten a teacher answer: drop an unfinished last sentence (cut at the token limit) and keep
    only the first sentence when the answer is longer than the acceptance limit."""
    sentences = _sentences(text.strip())
    if cut and len(sentences) > 1:
        sentences = sentences[:-1]
    joined = " ".join(sentences)
    if len(joined) > MAX_CHARS and sentences:
        return sentences[0]
    return joined
