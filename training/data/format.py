"""Chat formats of the fine-tuning tasks; the debugging agent asks with `fix_prompt` and, once a fix
passes, `explain_fix_prompt`.

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
# Run F: the same repair rows with the fix first and the diagnosis after it. In the order above the
# model names a bug type before it writes code, and on HumanEvalFix 123 of run E's 164 diagnoses are
# one of the four one-token mutation types; it then fixes 36 % against 63 % when asked for code only.
REPAIR_INSTRUCTION_CODE_FIRST = (
    "Respond with the complete fixed function in a ```python code block, then one line of JSON "
    '{"bug_location": "<the buggy line, verbatim>", "bug_type": "<short category>", '
    '"explanation": "<one or two sentences>"}.'
)


def code_first(messages: list[dict]) -> list[dict] | None:
    """A repair row (prompt ending with REPAIR_INSTRUCTION, answer JSON then code) in the code-first
    order; None for any other row."""
    *context, user, answer = messages
    head, sep, code = answer["content"].partition("\n```python\n")
    if not user["content"].endswith(REPAIR_INSTRUCTION) or not sep or not head.startswith("{"):
        return None
    prompt = user["content"][: -len(REPAIR_INSTRUCTION)] + REPAIR_INSTRUCTION_CODE_FIRST
    return [*context, {**user, "content": prompt}, {**answer, "content": f"```python\n{code.rstrip()}\n{head}"}]


def repair_prompt(buggy_code: str, test_name: str, test_code: str, error: str) -> str:
    return (
        "The following Python function has a bug.\n\n"
        f"```python\n{buggy_code.rstrip()}\n```\n\n"
        f"This test fails: `{test_name}`\n```python\n{test_code.rstrip()}\n```\n"
        f"Error:\n```\n{error.rstrip()}\n```\n\n"
        f"{REPAIR_INSTRUCTION}"
    )


def fix_prompt(function: str, code: str, tests: str, error: str | None = None) -> str:
    """The benchmark-style repair prompt (the v3 "benchmark" rows and HumanEvalFix): the answer is the
    fixed code only. On the same 164 HumanEvalFix bugs run E fixes 63 % with this prompt and 36 % with
    `repair_prompt`, where it has to name the bug before writing the fix. The error is added on a retry."""
    content = (
        f"Fix bugs in {function}.\n\n"
        f"```python\n{code.rstrip()}\n```\n\n"
        f"These tests fail:\n```python\n{tests.strip()}\n```\n\n"
    )
    if error is not None:
        content += f"Running the tests gives:\n```\n{error.strip()[:1500]}\n```\n\n"
    return content + "Return the complete fixed function in a markdown code block."


def explain_fix_prompt(buggy_code: str, fixed_code: str) -> str:
    """Asked after a fix passed its test, so the explanation describes the fix that works."""
    return (
        f"This Python function had a bug:\n\n```python\n{buggy_code.rstrip()}\n```\n\n"
        f"This version passes its test:\n\n```python\n{fixed_code.rstrip()}\n```\n\n"
        'Respond with one line of JSON {"bug_type": "<short category>", '
        '"explanation": "<one or two sentences: what was wrong and what the fix changes>"}.'
    )


def parse_explanation(text: str) -> dict | None:
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            candidate, _ = decoder.raw_decode(text, match.start())
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and isinstance(candidate.get("explanation"), str):
            return {"bug_type": str(candidate.get("bug_type", "")), "explanation": candidate["explanation"]}
    return None


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
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):  # decode from every brace: values may contain braces
        try:
            candidate, _ = decoder.raw_decode(text, match.start())
        except json.JSONDecodeError:
            continue
        if isinstance(candidate, dict) and "bug_location" in candidate:
            diagnosis = candidate
            break
    return diagnosis, extract_code(text)
