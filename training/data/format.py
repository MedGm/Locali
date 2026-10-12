"""Chat formats of the fine-tuning tasks; the debugging agent uses the same prompt and parser.

T1 answer format: one line of JSON with the diagnosis, then the complete fixed function in a
```python block. Code is not embedded in the JSON string: escaping whole functions inside JSON is
error-prone for small models, and the code block is what the evaluation extractor already reads.
"""

import json
import re

from evaluation.extract import extract_code

REPAIR_INSTRUCTION = (
    'Respond with one line of JSON {"bug_location": "<the buggy line, verbatim>", '
    '"bug_type": "<short category>", "explanation": "<one or two sentences>"}, '
    "then the complete fixed function in a ```python code block."
)


def repair_prompt(buggy_code: str, test_name: str, test_code: str, error: str) -> str:
    return (
        "The following Python function has a bug.\n\n"
        f"```python\n{buggy_code.rstrip()}\n```\n\n"
        f"This test fails: `{test_name}`\n```python\n{test_code.rstrip()}\n```\n"
        f"Error:\n```\n{error.rstrip()}\n```\n\n"
        f"{REPAIR_INSTRUCTION}"
    )


def template_explanation(example: dict) -> str:
    test = example["failing_test"]["name"].split("::")[-1]
    return (
        f"`{example['mutated_snippet']}` is a {example['bug_type']}, so `{test}` fails; "
        f"it should be `{example['original_snippet']}`."
    )


def t1_messages(example: dict, explanation: str) -> list[dict]:
    buggy_line = example["buggy_code"].splitlines()[example["line"] - 1]
    diagnosis = {"bug_location": buggy_line, "bug_type": example["bug_type"], "explanation": explanation}
    test = example["failing_test"]
    return [
        {"role": "user", "content": repair_prompt(example["buggy_code"], test["name"], test["code"], test["error"])},
        {"role": "assistant",
         "content": f"{json.dumps(diagnosis)}\n```python\n{example['fixed_code'].rstrip()}\n```"},
    ]


def parse_repair_answer(text: str) -> tuple[dict | None, str]:
    """(diagnosis or None, fixed code) from a T1-format answer."""
    diagnosis = None
    for match in re.finditer(r"\{[^{}\n]*\}", text):
        try:
            candidate = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and "bug_location" in candidate:
            diagnosis = candidate
            break
    return diagnosis, extract_code(text)
