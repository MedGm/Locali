"""Mixture v3r: mixture v3s plus real bugs (T1C) from ConDefects contests before 2024-02-01.

    uv run python -m training.data.build_mix_v3r --v3s data/mix_v3s --bugs data/real/bugs.jsonl --out data/mix_v3r

The real-bug rows (training.data.real_bugs) go through the same 13-gram decontamination against
every evaluation set, here including the 382 programs of the real-bug check, and are split by AtCoder task, so a task never appears in two splits. The v3s
rows are copied unchanged, so run G differs from run E only by these rows.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from evaluation.tasks.condefects import SINCE, DefectItem
from training.data.decontam import evaluation_index
from training.data.mix import assign_split
from training.data.real_bugs import MAX_CHARS, messages

ITEM_FIELDS = DefectItem.__dataclass_fields__
EVALUATION_ITEMS = Path("experiments/results/4_final_checks/condefects/items.jsonl")


def real_rows(bugs: list[dict], hits) -> tuple[list[dict], Counter]:
    """hits(text) -> names of the evaluation sets the text overlaps."""
    rows, dropped = [], Counter()
    for bug in bugs:
        item = DefectItem(**{k: v for k, v in bug.items() if k in ITEM_FIELDS})
        row = messages(item)
        if bug["verdict"] != "kept":
            dropped["not kept by the check"] += 1
        elif item.date >= SINCE:
            dropped["dated in the evaluation period"] += 1
        elif sum(len(m["content"]) for m in row) > MAX_CHARS:
            dropped["too long"] += 1
        elif found := hits(item.faulty + "\n" + item.correct):
            dropped.update(f"overlaps {name}" for name in found)
        else:
            group = "condefects:" + item.task_id.split("/")[0]
            rows.append({"id": "t1c-" + item.task_id.replace("/", "-"), "task": "T1C", "group": group,
                         "split": assign_split(group), "messages": row})
    return rows, dropped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--v3s", type=Path, required=True)
    parser.add_argument("--bugs", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    bugs = [json.loads(line) for line in args.bugs.read_text().splitlines() if line.strip()]
    index = evaluation_index()
    for line in EVALUATION_ITEMS.read_text().splitlines():  # the real-bug check itself: other tasks, same site
        item = json.loads(line)
        index.add("condefects", item["faulty"] + "\n" + item["correct"])
    rows, dropped = real_rows(bugs, index.sources)
    args.out.mkdir(parents=True, exist_ok=True)
    stats = {"bugs": len(bugs), "dropped": dict(dropped), "splits": {}}
    for split in ("train", "val", "test"):
        added = [r for r in rows if r["split"] == split]
        with (args.out / f"{split}.jsonl").open("w") as fh:
            fh.write((args.v3s / f"{split}.jsonl").read_text())
            for row in added:
                fh.write(json.dumps(row) + "\n")
        stats["splits"][split] = {"real_bugs": len(added), "tasks": len({r["group"] for r in added})}
    (args.out / "stats.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
