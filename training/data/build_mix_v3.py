"""Mixture v3: mixture v2 unchanged, plus the realistic bugs (T1R) from the teacher.

    uv run python -m training.data.build_mix_v3 --v2 data/mix_v2 --bugs data/v3/full/bugs.jsonl --out data/mix_v3

New examples go through the same 13-gram decontamination against every evaluation set and the same
group split as v2 (by CodeRM problem, so a problem never appears in two splits). The v2 rows are
copied as they are, so any difference between v2 and v3 comes from the T1R examples.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from training.data.decontam import evaluation_index
from training.data.mix import assign_split
from training.data.v3_repair import v3_format, v3_messages


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--v2", type=Path, required=True)
    parser.add_argument("--bugs", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    bugs = [json.loads(line) for path in args.bugs for line in path.read_text().splitlines() if line.strip()]
    index = evaluation_index()
    rows, dropped = [], Counter()
    for bug in bugs:
        hits = index.sources(bug["buggy_code"] + "\n" + bug["fixed_code"] + "\n" + bug["question"])
        if hits:
            dropped.update(hits)
            continue
        if not bug.get("description"):
            bug = bug | {"description": f"A {bug['kind'].replace('_', ' ')} bug makes the tests fail."}
        fmt = v3_format(bug)
        task_id = bug["source"].split(":")[-1]
        rows.append({"id": f"t1r-{task_id}", "task": "T1R", "group": bug["source"], "format": fmt,
                     "kind": bug["kind"], "split": assign_split(bug["source"]), "messages": v3_messages(bug, fmt)})

    args.out.mkdir(parents=True, exist_ok=True)
    counts = {}
    for split in ("train", "val", "test"):
        v2 = (args.v2 / f"{split}.jsonl").read_text().splitlines()
        new = [r for r in rows if r["split"] == split]
        with (args.out / f"{split}.jsonl").open("w") as fh:
            for line in v2:
                if line.strip():
                    fh.write(line + "\n")
            for r in new:
                fh.write(json.dumps({k: v for k, v in r.items() if k != "split"}) + "\n")
        counts[split] = {"v2": sum(1 for line in v2 if line.strip()), "t1r": len(new)}
    stats = {"bugs_in": len(bugs), "t1r_kept": len(rows), "decontam_dropped_by_source": dict(dropped),
             "splits": counts, "t1r_formats": dict(Counter(r["format"] for r in rows)),
             "t1r_kinds": dict(Counter(r["kind"] for r in rows)), "bugs_files": [str(p) for p in args.bugs]}
    (args.out / "stats.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
