"""Tables for capability study step 2 from the Kaggle job's outputs (training/kaggle/capability).

    uv run python experiments/scripts/capability_step2.py experiments/results/capability_study/step2_kaggle

Prints markdown: greedy pass@1 per prompt shape with paired tests, pass@k from the samples, and
how each model scores the others' greedy HumanEval+ answers.
"""

import json
import re
import statistics as st
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from evaluation.passk import pass_at_k
from experiments.scripts.paired_compare import compare_tasks

MODELS = {"qwen2.5-coder-3b": "base", "qwen2.5-coder-3b-ft-qlora-mixv3b-diag": "D",
          "qwen2.5-coder-3b-ft-qlora-mixv3s": "E"}
LOST = ["HumanEval/54", "HumanEval/55", "HumanEval/83", "HumanEval/86", "HumanEval/89", "HumanEval/97",
        "HumanEval/100", "HumanEval/141", "HumanEval/144", "HumanEval/154"]
GAINED = ["HumanEval/59", "HumanEval/64", "HumanEval/99", "HumanEval/160"]
# The base opens its answers with "```\npython\n", the fine-tuned models with "```python\n"; the
# first 3 answer tokens are that fence and cost ~10 nats under the other style, so they are skipped.
SKIP = 3


def comments(code: str) -> bool:
    code = re.sub(r'(""".*?"""|\'\'\'.*?\'\'\')', "", code, flags=re.DOTALL)
    return any(line.strip().startswith("#") or " # " in line for line in code.splitlines())


def load(root: Path, task: str, model: str) -> list[dict]:
    path = next((root / "results" / task).glob(f"{model}__*")) / "samples.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def greedy(root: Path) -> None:
    print("## Greedy pass@1 by prompt shape\n")
    print("| Model | HumanEval+ code (std) | HumanEval+ English | p | MBPP+ English (std) | MBPP+ code stub | p |")
    print("|---|---|---|---|---|---|---|")
    res = root / "results"
    for model, name in MODELS.items():
        he = compare_tasks(res, model, "humaneval_plus", res, model, "humaneval_plus_english")
        mb = compare_tasks(res, model, "mbpp_plus", res, model, "mbpp_plus_stub")
        print(f"| {name} | {he['a']:.1%} | {he['b']:.1%} | {he['p']:.3g} ({he['only_a']}/{he['only_b']}) "
              f"| {mb['a']:.1%} | {mb['b']:.1%} | {mb['p']:.3g} ({mb['only_a']}/{mb['only_b']}) |")
    print("\n| Model, task | answers with comments | output tokens |\n|---|---|---|")
    for task in ("humaneval_plus", "humaneval_plus_english", "mbpp_plus", "mbpp_plus_stub"):
        for model, name in MODELS.items():
            rows = load(root, task, model)
            print(f"| {name}, {task} | {sum(comments(r['code']) for r in rows) / len(rows):.2f} "
                  f"| {st.mean(int(r['output_tokens']) for r in rows):.0f} |")
    print("\n| Model vs base, paired | HumanEval+ code | HumanEval+ English | MBPP+ English | MBPP+ code stub |")
    print("|---|---|---|---|---|")
    for model, name in list(MODELS.items())[1:]:
        cells = []
        for task in ("humaneval_plus", "humaneval_plus_english", "mbpp_plus", "mbpp_plus_stub"):
            c = compare_tasks(res, "qwen2.5-coder-3b", task, res, model, task)
            cells.append(f"{c['b'] - c['a']:+.1%} ({c['only_a']}/{c['only_b']}, p {c['p']:.3g})")
        print(f"| {name} | " + " | ".join(cells) + " |")
    print("\nLost / gained problems, English prompt (pass = 1):\n")
    for model, name in MODELS.items():
        std = {r["task_id"]: r["passed"] for r in load(root, "humaneval_plus", model)}
        eng = {r["task_id"]: r["passed"] for r in load(root, "humaneval_plus_english", model)}
        print(f"- {name}: lost-10 code {sum(std.get(t, False) for t in LOST)}, English {sum(eng.get(t, False) for t in LOST)}; "
              f"gained-4 code {sum(std.get(t, False) for t in GAINED)}, English {sum(eng.get(t, False) for t in GAINED)}")


def samples(root: Path) -> None:
    print("\n## Sampling, HumanEval+ standard prompt, T = 0.8\n")
    print("| Model | pass@1 | pass@5 | pass@20 | lost-10 solved at least once | lost-10 pass rate |")
    print("|---|---|---|---|---|---|")
    per = {}
    for model, name in MODELS.items():
        by = defaultdict(list)
        for r in map(json.loads, (root / "samples" / f"{model}.jsonl").read_text().splitlines()):
            by[r["task_id"]].append(r["passed"])
        per[name] = by
        n = len(next(iter(by.values())))
        at = {k: st.mean(pass_at_k(n, sum(v), k) for v in by.values()) for k in (1, 5, n)}
        lost_any = sum(any(by.get(t, [])) for t in LOST)
        lost_rate = st.mean(sum(by.get(t, [])) / n for t in LOST)
        print(f"| {name} | {at[1]:.1%} | {at[5]:.1%} | {at[n]:.1%} | {lost_any}/10 | {lost_rate:.0%} |")
    print("\nPer lost problem, samples passing out of 20 (base / D / E):\n")
    for t in LOST + GAINED:
        print(f"- {t}{' (gained)' if t in GAINED else ''}: " + " / ".join(str(sum(per[m].get(t, []))) for m in per))


def body(row: dict) -> list[float]:
    return row["token_logprobs"][SKIP:]


def logprobs(root: Path) -> None:
    rows = [json.loads(line) for line in (root / "logprobs.jsonl").read_text().splitlines()]
    key = {(r["model"], r["source"], r["task_id"]): r for r in rows}
    print(f"\n## Log-probability of each model's greedy HumanEval+ answer, without the first {SKIP} tokens\n")
    print("Mean per token, and in brackets the share of tokens below -2.\n")
    print("| Scored by \\ answer of | " + " | ".join(MODELS.values()) + " |")
    print("|---|" + "---|" * len(MODELS))
    for m, name in MODELS.items():
        cells = []
        for s in MODELS:
            toks = [t for r in rows if r["model"] == m and r["source"] == s for t in body(r)]
            cells.append(f"{st.mean(toks):.3f} ({sum(t < -2 for t in toks) / len(toks):.1%})")
        print(f"| {name} | " + " | ".join(cells) + " |")
    base, d, e = MODELS
    greedy = {m: {r["task_id"]: r["passed"] for r in load(root, "humaneval_plus", m)} for m in (base, d)}
    groups = defaultdict(list)
    for t, ok in greedy[base].items():
        if (d, base, t) not in key:
            continue
        group = "lost by D" if ok and not greedy[d][t] else "both pass" if ok and greedy[d][t] else "other"
        groups[group].append(sum(body(key[(d, base, t)])) - sum(body(key[(base, base, t)])))
    print("\nNats the base's answer loses when D scores it instead of the base (median):\n")
    for group, v in sorted(groups.items()):
        print(f"- {group} ({len(v)} problems): {st.median(v):.1f}")
    print("\nLost-10: total log-probability of the base's (correct) answer under each model, the number of its"
          " tokens below -2 under D and E, and D's and E's own answers:\n")
    print("| Problem | tokens | base answer under base / D / E | tokens < -2 under D / E | D own | E own |")
    print("|---|---|---|---|---|---|")
    for t in LOST:
        if (d, base, t) not in key:
            continue
        under = " / ".join(f"{sum(body(key[(m, base, t)])):.1f}" for m in MODELS)
        low = " / ".join(str(sum(v < -2 for v in body(key[(m, base, t)]))) for m in (d, e))
        print(f"| {t} | {key[(base, base, t)]['n_tokens']} | {under} | {low} "
              f"| {sum(body(key[(d, d, t)])):.1f} | {sum(body(key[(e, e, t)])):.1f} |")

if __name__ == "__main__":
    root = Path(sys.argv[1])
    greedy(root)
    samples(root)
    logprobs(root)
