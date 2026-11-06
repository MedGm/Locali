"""Tables for capability study step 3 from the forced-divergence walks (training/kaggle/evaluate/divergence).

    uv run python experiments/scripts/stats/capability_step3.py experiments/results/3_finetune_3b/capability_study/step3_kaggle

Prints markdown: per direction, how many forced tokens turn a failing answer into a passing one,
where the leader's token ranks for the follower at each divergence, and the first divergences on
the 10 problems all fine-tuned runs lose (step 1).
"""

import json
import statistics as st
import sys
from collections import Counter
from pathlib import Path

NAMES = {"qwen2.5-coder-3b": "base", "qwen2.5-coder-3b-ft-qlora-mixv3b-diag": "D",
         "qwen2.5-coder-3b-ft-qlora-mixv3s": "E"}
LOST = ["HumanEval/54", "HumanEval/55", "HumanEval/83", "HumanEval/86", "HumanEval/89", "HumanEval/97",
        "HumanEval/100", "HumanEval/141", "HumanEval/144", "HumanEval/154"]
BINS = (("1", 1, 1), ("2", 2, 2), ("3-5", 3, 5), ("6-12", 6, 12))


def forced_to_pass(walk: dict) -> int | None:
    return walk["steps"][-1]["forced"] if walk["passed"] else None


def rank_bin(rank: int | None) -> str:
    return "not in top 5" if rank is None else str(rank) if rank <= 3 else "4-5"


def directions(walks: list[dict]) -> None:
    print("## Forced tokens until the follower's answer passes\n")
    print("| Follower ← leader | walks | first answer = step 2 greedy | passes with 0 forced |"
          + "".join(f" {b} forced |" for b, _, _ in BINS) + " not within 12 |")
    print("|---|---|---|---|" + "---|" * len(BINS) + "---|")
    for (f, lead), rows in grouped(walks).items():
        need = [forced_to_pass(w) for w in rows]
        same = sum(w["steps"][0].get("same_as_step2_greedy", False) for w in rows)
        cells = [sum(n is not None and lo <= n <= hi for n in need) for _, lo, hi in BINS]
        print(f"| {NAMES[f]} ← {NAMES[lead]} | {len(rows)} | {same} | {need.count(0)} | "
              + " | ".join(map(str, cells)) + f" | {need.count(None)} |")


def grouped(walks: list[dict]) -> dict[tuple[str, str], list[dict]]:
    out: dict[tuple[str, str], list[dict]] = {}
    for w in walks:
        out.setdefault((w["follower"], w["leader"]), []).append(w)
    return out


def ranks(walks: list[dict]) -> None:
    print("\n## Rank of the leader's token among the follower's top 5, at each divergence\n")
    print("Raw log-probabilities. vLLM applied the model's generation_config (repetition penalty 1.05), so the"
          " leader's token can rank 1 when the penalty made the follower choose another.\n")
    order = ["1", "2", "3", "4-5", "not in top 5"]
    print("| Follower ← leader | divergences | " + " | ".join(f"rank {o}" for o in order)
          + " | median log-prob gap (follower's token − leader's) |")
    print("|---|---|" + "---|" * len(order) + "---|")
    for (f, lead), rows in grouped(walks).items():
        divs = [s["divergence"] for w in rows for s in w["steps"] if "divergence" in s]
        c = Counter(rank_bin(d["leader_rank"]) for d in divs)
        gaps = [d["follower_logprob"] - d["leader_logprob"] for d in divs if d["leader_logprob"] is not None]
        gap = f"{st.median(gaps):.2f}" if gaps else "–"
        print(f"| {NAMES[f]} ← {NAMES[lead]} | {len(divs)} | " + " | ".join(str(c[o]) for o in order) + f" | {gap} |")


def controls(walks: list[dict]) -> None:
    print("\n## Control: does any single nudge fix the answer?\n")
    print("One forced token each. Leader: the leader's token at the first divergence. Uncertain: the follower's"
          " own second choice at one of its 5 least sure positions. Random: its second choice at a random"
          " position.\n")
    print("| Follower ← leader | leader's token at first divergence | uncertain nudge | random nudge |")
    print("|---|---|---|---|")
    for (f, lead), rows in grouped(walks).items():
        first = [forced_to_pass(w) is not None and forced_to_pass(w) <= 1 for w in rows]
        cells = [f"{sum(first)}/{len(first)} ({sum(first) / len(first):.0%})"]
        for kind in ("uncertain", "random"):
            c = [x["passed"] for w in rows for x in w.get("controls", []) if x["kind"] == kind]
            cells.append(f"{sum(c)}/{len(c)} ({sum(c) / len(c):.0%})" if c else "–")
        print(f"| {NAMES[f]} ← {NAMES[lead]} | " + " | ".join(cells) + " |")


def line_kind(d: dict) -> str:
    """What the leader writes at a divergence: docstring or comment, import, signature, or code."""
    line = (d["line_before"] + d["leader_rest_of_line"]).strip()
    if line.startswith(('"""', "'\'\'", "#")) or (not d["line_before"].strip() and '"""' in line):
        return "docstring or comment"
    if line.startswith(("import ", "from ")):
        return "import"
    if line.startswith("def ") and d["line_before"].strip().startswith("def "):
        return "signature"
    return "code"


def kinds(walks: list[dict]) -> None:
    print("\n## What the leader writes at the first divergence\n")
    order = ["docstring or comment", "import", "signature", "code"]
    print("| Follower ← leader | " + " | ".join(order) + " |")
    print("|---|" + "---|" * len(order))
    for (f, lead), rows in grouped(walks).items():
        firsts = [next((s["divergence"] for s in w["steps"] if "divergence" in s), None) for w in rows]
        c = Counter(line_kind(d) for d in firsts if d)
        print(f"| {NAMES[f]} ← {NAMES[lead]} | " + " | ".join(str(c[o]) for o in order) + " |")


def lost(walks: list[dict]) -> None:
    print("\n## The lost 10: follower D or E, leader base\n")
    print("| Problem | follower | forced to pass | first divergence: leader's line vs follower's line | leader rank |")
    print("|---|---|---|---|---|")
    for t in LOST:
        for w in walks:
            if w["task_id"] != t or NAMES[w["leader"]] != "base":
                continue
            first = next((s["divergence"] for s in w["steps"] if "divergence" in s), None)
            need = forced_to_pass(w)
            if first:
                before = first["line_before"].strip()
                cell = (f"`{before}` + `{first['leader_rest_of_line']}` vs `{first['follower_rest_of_line']}`"
                        .replace("|", "\\|"))
                rank = rank_bin(first["leader_rank"])
            else:
                cell, rank = "–", "–"
            print(f"| {t} | {NAMES[w['follower']]} | {'not within 12' if need is None else need} | {cell} | {rank} |")


if __name__ == "__main__":
    root = Path(sys.argv[1])
    walks = [json.loads(line) for line in (root / "walks.jsonl").read_text().splitlines() if line.strip()]
    directions(walks)
    ranks(walks)
    controls(walks)
    kinds(walks)
    lost(walks)
