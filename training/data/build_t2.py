"""Build T2 (test generation) examples.

    uv run python -m training.data.build_t2 --seeds 40 --out data/t2/pilot.jsonl

Seeds are sampled with a different seed than T1 so the two tasks cover more distinct problems.
"""

import argparse
import json
import time
from pathlib import Path

from training.data.t1_bugs import SOURCE, SOURCE_REVISION, select_seeds
from training.data.t2_tests import build_t2_examples

T2_SAMPLE_SEED = 11


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    from datasets import load_dataset

    rows = load_dataset(SOURCE, revision=SOURCE_REVISION, split="train")
    start = time.perf_counter()
    seeds = select_seeds(rows, n=args.seeds, seed=T2_SAMPLE_SEED)
    examples, stats = build_t2_examples(seeds, workers=args.workers)
    stats.update({"seeds_selected": len(seeds), "wall_s": round(time.perf_counter() - start, 1),
                  "source": SOURCE, "revision": SOURCE_REVISION, "sample_seed": T2_SAMPLE_SEED})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(ex) + "\n" for ex in examples))
    args.out.with_suffix(".stats.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
