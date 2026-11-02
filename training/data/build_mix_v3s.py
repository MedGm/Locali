"""Mixture v3s: mixture v3b with self-distilled replay answers.

    uv run python -m training.data.build_mix_v3s --v3b data/mix_v3b \
        --answers data/selfdistill/answers.jsonl --out data/mix_v3s

Each replay answer (self-oss-instruct, written by StarCoder2-15B) is replaced by the base
Qwen2.5-Coder-3B's answer to the same prompt when that answer passed the Kaggle check
(training/kaggle/selfdistill: finished, parses, runs without error) and shares no 13-gram with an
evaluation set. All other rows, and replay rows without such an answer, are copied unchanged.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from training.data.decontam import evaluation_index
from training.data.selfdistill import replace_replay


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--v3b", type=Path, required=True)
    parser.add_argument("--answers", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    answers = [json.loads(line) for line in args.answers.read_text().splitlines() if line.strip()]
    status = Counter(a["status"] for a in answers)
    index = evaluation_index()
    accepted, contaminated = {}, Counter()
    for a in answers:
        if a["status"] != "passed":
            continue
        hits = index.sources(a["text"])
        if hits:
            contaminated.update(hits)
            continue
        accepted[a["id"]] = a["text"]

    args.out.mkdir(parents=True, exist_ok=True)
    splits = {}
    for split in ("train", "val", "test"):
        rows = [json.loads(line) for line in (args.v3b / f"{split}.jsonl").read_text().splitlines() if line.strip()]
        rows, replaced = replace_replay(rows, accepted)
        with (args.out / f"{split}.jsonl").open("w") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")
        splits[split] = {"rows": len(rows), "replay": sum(r["task"] == "replay" for r in rows),
                         "replay_self_distilled": replaced}
    stats = {"answers": len(answers), "answer_status": dict(status), "decontam_dropped_by_source": dict(contaminated),
             "accepted": len(accepted), "splits": splits}
    (args.out / "stats.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
