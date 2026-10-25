"""Mixture v3: mixture v2 unchanged, plus the realistic bugs (T1R) from the teacher.

    uv run python -m training.data.build_mix_v3 --v2 data/mix_v2 --bugs data/v3/full/bugs.jsonl --out data/mix_v3
    uv run python -m training.data.build_mix_v3 --v2 data/mix_v2 --bugs data/v3/full/bugs.jsonl \
        --t1-keep 0.5 --replay-total 4000 --out data/mix_v3b

--t1-keep keeps that share of the v2 mutation repair rows (T1), chosen by problem; --replay-total
raises the general-instruction replay set to that many rows, adding the next rows of the same
self-oss source (decontaminated like the rest).

New examples go through the same 13-gram decontamination against every evaluation set and the same
group split as v2 (by CodeRM problem, so a problem never appears in two splits). The v2 rows are
copied as they are, so any difference between v2 and v3 comes from the T1R examples.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from training.data.decontam import evaluation_index
from training.data.mix import _bucket, assign_split
from training.data.v3_repair import first_changed_line, template_diagnosis, v3_format, v3_messages


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--v2", type=Path, required=True)
    parser.add_argument("--bugs", type=Path, nargs="+", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--t1-keep", type=float, default=1.0)
    parser.add_argument("--replay-total", type=int, default=0)
    parser.add_argument("--diagnoses", type=Path, help="reviewer diagnoses per bug (source, diagnosis)")
    args = parser.parse_args()

    bugs = [json.loads(line) for path in args.bugs for line in path.read_text().splitlines() if line.strip()]
    diagnoses = {}
    if args.diagnoses:
        diagnoses = {r["source"]: r["diagnosis"] for r in map(json.loads, args.diagnoses.read_text().splitlines())}
    index = evaluation_index()
    rows, dropped = [], Counter()
    for bug in bugs:
        hits = index.sources(bug["buggy_code"] + "\n" + bug["fixed_code"] + "\n" + bug["question"])
        if hits:
            dropped.update(hits)
            continue
        if not bug.get("description"):
            bug = bug | {"description": f"A {bug['kind'].replace('_', ' ')} bug makes the tests fail."}
        if args.diagnoses:
            line = first_changed_line(bug["fixed_code"], bug["buggy_code"])
            bug = bug | {"diagnosis": diagnoses.get(bug["source"]) or template_diagnosis(line, bug["kind"])}
        fmt = v3_format(bug)
        task_id = bug["source"].split(":")[-1]
        rows.append({"id": f"t1r-{task_id}", "task": "T1R", "group": bug["source"], "format": fmt,
                     "kind": bug["kind"], "split": assign_split(bug["source"]), "messages": v3_messages(bug, fmt)})

    extra_replay = []
    if args.replay_total:
        from datasets import load_dataset

        from training.data.selfoss import SELF_OSS, replay_examples

        have = {json.loads(line)["id"] for split in ("train", "val", "test")
                for line in (args.v2 / f"{split}.jsonl").read_text().splitlines() if line.strip()}
        source = load_dataset(SELF_OSS[0], revision=SELF_OSS[1], split="train")
        for ex in replay_examples(source, args.replay_total):
            if ex["id"] in have or index.sources(ex["messages"][0]["content"] + "\n" + ex["messages"][1]["content"]):
                continue
            extra_replay.append({k: ex[k] for k in ("id", "task", "group", "messages")}
                                | {"split": assign_split(ex["group"])})
        rows.extend(extra_replay)

    def keep_v2(line: str) -> bool:
        row = json.loads(line)
        return row["task"] != "T1" or _bucket("v3b-t1", row["group"], 1000) < args.t1_keep * 1000

    args.out.mkdir(parents=True, exist_ok=True)
    counts = {}
    for split in ("train", "val", "test"):
        v2 = [line for line in (args.v2 / f"{split}.jsonl").read_text().splitlines()
              if line.strip() and (split != "train" or keep_v2(line))]
        new = [r for r in rows if r["split"] == split]
        with (args.out / f"{split}.jsonl").open("w") as fh:
            for line in v2:
                if line.strip():
                    fh.write(line + "\n")
            for r in new:
                fh.write(json.dumps({k: v for k, v in r.items() if k != "split"}) + "\n")
        counts[split] = {"v2": len(v2), "t1r": sum(r["task"] == "T1R" for r in new),
                         "extra_replay": sum(r["task"] == "replay" for r in new)}
    stats = {"bugs_in": len(bugs), "t1r_kept": sum(r["task"] == "T1R" for r in rows),
             "t1_keep": args.t1_keep, "extra_replay": len(extra_replay), "decontam_dropped_by_source": dict(dropped),
             "splits": counts, "t1r_formats": dict(Counter(r["format"] for r in rows if r["task"] == "T1R")),
             "t1r_kinds": dict(Counter(r["kind"] for r in rows if r["task"] == "T1R")), "bugs_files": [str(p) for p in args.bugs],
             "diagnoses": str(args.diagnoses) if args.diagnoses else None}
    (args.out / "stats.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
