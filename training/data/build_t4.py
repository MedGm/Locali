"""Build T4 (execution trace) examples, decontaminated against every evaluation set.

    uv run python -m training.data.build_t4 --seeds 150 --out data/t4/pilot.jsonl

Seeds are sampled with their own seed so T4 covers problems beyond those of T1 and T2; the
group-level split still keeps each problem on one side of train/test across all tasks.
"""

import argparse
import ast
import collections
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from training.data.decontam import evaluation_index
from training.data.t1_bugs import SOURCE, SOURCE_REVISION, select_seeds
from training.data.t4_trace import trace_seed

T4_SAMPLE_SEED = 23


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, required=True)
    parser.add_argument("--calls-per-seed", type=int, default=1)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    from datasets import load_dataset

    rows = load_dataset(SOURCE, revision=SOURCE_REVISION, split="train")
    start = time.perf_counter()
    seeds = select_seeds(rows, n=args.seeds, seed=T4_SAMPLE_SEED)
    with ThreadPoolExecutor(args.workers) as pool:
        per_seed = list(pool.map(lambda s: trace_seed(s, max_calls=args.calls_per_seed), seeds))
    index = evaluation_index()
    examples, dropped = [], collections.Counter()
    for ex in (ex for batch in per_seed for ex in batch):
        hits = index.sources(ex["code"])
        if hits:
            dropped.update(hits)
            continue
        examples.append(ex)
    stats = {"seeds_selected": len(seeds), "seeds_with_example": sum(bool(b) for b in per_seed),
             "examples": len(examples), "decontamination_dropped": dict(dropped),
             "output_types": dict(collections.Counter(type(ast.literal_eval(ex["output"])).__name__ for ex in examples)),
             "wall_s": round(time.perf_counter() - start, 1), "source": SOURCE, "revision": SOURCE_REVISION,
             "sample_seed": T4_SAMPLE_SEED}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(ex) + "\n" for ex in examples))
    args.out.with_suffix(".stats.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
