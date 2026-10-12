"""Build T1 (bug repair) raw examples.

    uv run python -m training.data.build_t1 --seeds 40 --out data/t1/pilot.jsonl

Writes examples as JSONL (data/ is not versioned; datasets are published to the Hugging Face Hub)
and a stats file next to them.
"""

import argparse
import json
import time
from pathlib import Path

from training.data.t1_bugs import SOURCE, SOURCE_REVISION, build_examples, select_seeds


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, required=True)
    parser.add_argument("--mutants-per-seed", type=int, default=2)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    from datasets import load_dataset

    rows = load_dataset(SOURCE, revision=SOURCE_REVISION, split="train")
    start = time.perf_counter()
    seeds = select_seeds(rows, n=args.seeds)
    examples, stats = build_examples(seeds, mutants_per_seed=args.mutants_per_seed, workers=args.workers)
    stats.update({"seeds_selected": len(seeds), "wall_s": round(time.perf_counter() - start, 1),
                  "source": SOURCE, "revision": SOURCE_REVISION})

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(ex) + "\n" for ex in examples))
    args.out.with_suffix(".stats.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
