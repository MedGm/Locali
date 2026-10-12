"""Assemble the fine-tuning mixture (v1) from the task builders' outputs.

    uv run python -m training.data.build_mix --t1 data/t1/mutation_v1.notimeout.clean.jsonl \
        --t2 data/t2/tests_v1.clean.jsonl --explanations data/teacher/explanations.jsonl --out data/mix_v1

Writes <out>/{train,val,test}.jsonl with {id, task, group, split, messages} and <out>/stats.json.
All component logic lives in tested modules; this script only wires them together.
"""

import argparse
import collections
import json
from pathlib import Path

from training.data.decontam import evaluation_index
from training.data.format import t1_messages
from training.data.mix import assign_split, explanation_for, reserved_for_t3
from training.data.selfoss import SELF_OSS, replay_examples, review_items
from training.data.t2_tests import t2_messages
from training.data.t3_review import t3_items_from_bug_pair, t3_messages


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--t1", type=Path, required=True)
    parser.add_argument("--t2", type=Path, required=True)
    parser.add_argument("--explanations", type=Path)
    parser.add_argument("--t3-pairs", type=int, default=1000)
    parser.add_argument("--t3-corpus", nargs=3, type=int, default=[500, 250, 250], metavar=("SECURITY", "QUALITY", "CLEAN"))
    parser.add_argument("--replay", type=int, default=2000)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    from datasets import load_dataset

    teacher = {r["id"]: r for r in _jsonl(args.explanations)} if args.explanations else {}
    origins = collections.Counter()
    examples: list[dict] = []

    t3_pairs = 0
    for ex in _jsonl(args.t1):
        row = teacher.get(ex["id"], {})
        explanation, origin = explanation_for(ex, row.get("text"), cut=row.get("finish_reason") == "length")
        origins[origin] += 1
        if reserved_for_t3(ex["source"]):
            if t3_pairs >= args.t3_pairs:
                continue
            t3_pairs += 1
            for item in t3_items_from_bug_pair(ex, explanation):
                examples.append({"id": item["id"], "task": "T3", "group": item["group"], "messages": t3_messages(item),
                                 "has_findings": bool(item["findings"]), "has_bug": any(f["category"] == "bug" for f in item["findings"])})
        else:
            examples.append({"id": ex["id"], "task": "T1", "group": ex["source"], "messages": t1_messages(ex, explanation)})

    for ex in _jsonl(args.t2):
        examples.append({"id": ex["id"], "task": "T2", "group": ex["source"], "messages": t2_messages(ex)})

    rows = load_dataset(SELF_OSS[0], revision=SELF_OSS[1], split="train")
    index = evaluation_index()
    dropped = collections.Counter()
    for item in review_items(rows, *args.t3_corpus):
        if index.sources(item["code"]):
            dropped["T3-corpus"] += 1
            continue
        examples.append({"id": item["id"], "task": "T3", "group": item["group"], "messages": t3_messages(item),
                         "has_findings": bool(item["findings"]), "has_bug": False})
    for ex in replay_examples(rows, args.replay):
        if index.sources(ex["messages"][0]["content"] + "\n" + ex["messages"][1]["content"]):
            dropped["replay"] += 1
            continue
        examples.append({k: ex[k] for k in ("id", "task", "group", "messages")})

    args.out.mkdir(parents=True, exist_ok=True)
    by_split: dict[str, list[dict]] = collections.defaultdict(list)
    for ex in examples:
        ex["split"] = assign_split(ex["group"])
        by_split[ex["split"]].append(ex)
    for split, rows_out in by_split.items():
        (args.out / f"{split}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows_out))

    t3 = [e for e in examples if e["task"] == "T3"]
    stats = {
        "counts": {s: dict(collections.Counter(e["task"] for e in rows_out)) for s, rows_out in by_split.items()},
        "total": len(examples),
        "explanations": dict(origins),
        "t3_balance": {"with_bug": sum(e["has_bug"] for e in t3), "without_any_finding": sum(not e["has_findings"] for e in t3),
                       "total": len(t3)},
        "decontamination_dropped": dict(dropped),
        "groups_in_more_than_one_split": 0,
    }
    splits_per_group = collections.defaultdict(set)
    for e in examples:
        splits_per_group[e["group"]].add(e["split"])
    stats["groups_in_more_than_one_split"] = sum(len(s) > 1 for s in splits_per_group.values())
    (args.out / "stats.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
