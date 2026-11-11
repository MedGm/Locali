"""Mixture v3f: mixture v3s with every repair-format row answered code first.

    uv run python -m training.data.build_mix_v3f --v3s data/mix_v3s --out data/mix_v3f

The T1 (mutation) and T1R "repair" rows ask for a JSON diagnosis and then the fixed function. Here
the same rows ask for the fixed function and then the diagnosis (training.data.format.code_first):
same code, same diagnosis text, only the order and the instruction sentence change. All other rows
are copied unchanged, so run F differs from run E in this one thing.
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from training.data.format import code_first


def reorder(rows: list[dict]) -> tuple[list[dict], Counter]:
    out, changed = [], Counter()
    for row in rows:
        messages = code_first(row["messages"])
        if messages is not None:
            row = {**row, "messages": messages}
            changed[row["task"]] += 1
        out.append(row)
    return out, changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--v3s", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    stats = {}
    for split in ("train", "val", "test"):
        rows = [json.loads(line) for line in (args.v3s / f"{split}.jsonl").read_text().splitlines() if line.strip()]
        rows, changed = reorder(rows)
        with (args.out / f"{split}.jsonl").open("w") as fh:
            for row in rows:
                fh.write(json.dumps(row) + "\n")
        stats[split] = {"rows": len(rows), "code_first": dict(changed)}
    (args.out / "stats.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
