"""CRUXEval-O: predict a function's output for a given input (code reasoning).

Gu et al., 2024, "CRUXEval: A Benchmark for Code Reasoning, Understanding and Execution".
Prompt, answer post-processing and scoring follow the official repository
(prompts.make_direct_output_prompt, tasks/output_prediction.py, evaluation/utils_general.py),
adapted to chat: the prompt is sent as a user message instead of a text-completion prefix.
"""

import re
from dataclasses import dataclass

from evaluation.client import Completion
from evaluation.passk import pass_at_k
from evaluation.tasks.codegen import run_program

CRUXEVAL = ("cruxeval-org/cruxeval", "b96af0450242eb4da433032b90998f25588a5d0f")

_PROMPT = """You are given a Python function and an assertion containing an input to the function. Complete the assertion with a literal (no unsimplified expressions, no function calls) containing the output when executing the provided code on the given input, even if the function is incorrect or incomplete. Do NOT output any extra information. Provide the full assertion with the correct output in [ANSWER] and [/ANSWER] tags, following the examples.

[PYTHON]
def f(n):
    return n
assert f(17) == ??
[/PYTHON]
[ANSWER]
assert f(17) == 17
[/ANSWER]

[PYTHON]
def f(s):
    return s + "a"
assert f("x9j") == ??
[/PYTHON]
[ANSWER]
assert f("x9j") == "x9ja"
[/ANSWER]

[PYTHON]
{code}
assert f({input}) == ??
[/PYTHON]
[ANSWER]
"""

_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)


@dataclass
class CruxItem:
    task_id: str
    code: str
    input: str
    output: str


def parse_prediction(text: str) -> str:
    text = _THINK.sub("", text)
    if "[ANSWER]" in text:
        text = text.split("[ANSWER]", 1)[1]
    text = text.split("[/ANSWER]", 1)[0]
    text = re.sub(r"```[a-zA-Z]*", "", text)
    if "==" in text:
        text = text.split("==", 1)[1]
    return text.strip()


class CruxOutputTask:
    name = "cruxeval_o"
    dataset = CRUXEVAL

    @property
    def excluded(self) -> dict[str, str]:
        return {}

    def load(self, limit: int | None = None) -> list[CruxItem]:
        from datasets import load_dataset

        repo, revision = CRUXEVAL
        rows = load_dataset(repo, revision=revision, split="test")
        if limit:
            rows = rows.select(range(min(limit, len(rows))))
        return [CruxItem(r["id"], r["code"], r["input"], r["output"]) for r in rows]

    def messages(self, item: CruxItem) -> list[dict]:
        return [{"role": "user", "content": _PROMPT.format(code=item.code, input=item.input)}]

    def score(self, item: CruxItem, completion: Completion, eval_timeout_s: float) -> dict:
        prediction = parse_prediction(completion.text)
        # Official rule: an answer that just calls the function on the input does not count.
        if not prediction or f"f({item.input})" in prediction:
            return {"status": "invalid", "passed": False, "prediction": prediction, "eval_duration_s": 0.0}
        outcome = run_program(f"{item.code}\nassert {item.output} == {prediction}\n", eval_timeout_s)
        return {
            "status": outcome.status,
            "passed": outcome.passed,
            "prediction": prediction,
            "eval_duration_s": outcome.duration_s,
        }

    def metrics(self, records: list[dict]) -> dict:
        n, passed = len(records), sum(r["passed"] for r in records)
        return {"pass@1": round(pass_at_k(n, passed, 1), 4) if n else None}

    def reference(self, item: CruxItem) -> str:
        return f"assert f({item.input}) == {item.output}\n[/ANSWER]"


CRUX_OUTPUT_TASK = CruxOutputTask()
