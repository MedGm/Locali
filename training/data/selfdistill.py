"""Self-distilled replay: the base model's own answers to the replay prompts.

The replay rows (self-oss-instruct, answers written by StarCoder2-15B) are there against
forgetting, but they also teach StarCoder2's answer style. Every fine-tuned 3B run loses 6 to 9
points on HumanEval+ (experiments/results/3_finetune_3b/keepdoc_t4); this replaces each replay answer with the
base Qwen2.5-Coder-3B's own answer when that answer finished, contains Python that parses, and runs
without error (checked in the Kaggle job, evaluation/isolated.py). Otherwise the original stays.
The dataset has no tests, so "runs without error" is the only check of correctness.
"""

import ast
import copy

from evaluation.extract import python_blocks


def replay_prompts(rows: list[dict]) -> list[tuple[str, list[dict]]]:
    """(id, messages without the answer) for every replay row."""
    return [(r["id"], r["messages"][:-1]) for r in rows if r["task"] == "replay"]


def runnable_code(answer: dict) -> str | None:
    """The code to execute for a generated answer, or None if the answer is rejected outright."""
    if answer.get("finish_reason") != "stop":
        return None
    blocks = python_blocks(answer.get("text", ""))
    if not blocks:
        return None
    code = "\n\n".join(blocks)
    try:
        ast.parse(code)
    except SyntaxError:
        return None
    return code


def replace_replay(rows: list[dict], accepted: dict[str, str]) -> tuple[list[dict], int]:
    """Copy of rows with the answer of each replay row in `accepted` replaced; number replaced."""
    out, replaced = [], 0
    for row in rows:
        if row["task"] == "replay" and row["id"] in accepted:
            row = copy.deepcopy(row)
            row["messages"][-1] = {"role": "assistant", "content": accepted[row["id"]]}
            replaced += 1
        out.append(row)
    return out, replaced
