"""Build T1 (bug repair) raw examples.

    uv run python -m training.data.build_t1 --seeds 40 --out data/t1/pilot.jsonl
    uv run python -m training.data.build_t1 --family v2 --sample-seed 29 --seeds 1200 --out data/t1/mutation_v2ops.jsonl

Writes examples as JSONL (data/ is not versioned; datasets are published to the Hugging Face Hub)
and a stats file next to them.
"""

import argparse
import json
import time
from collections import Counter
from pathlib import Path

from training.data.t1_bugs import SOURCE, SOURCE_REVISION, build_examples, select_seeds


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, required=True)
    parser.add_argument("--mutants-per-seed", type=int, default=2)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--family", choices=["v1", "v2"], default="v1", help="mutation operator family")
    parser.add_argument("--max-per-operator", type=int, help="keep at most N examples per operator, in file order")
    parser.add_argument("--sample-seed", type=int, default=3407, help="seed for sampling problems")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    from datasets import load_dataset

    rows = load_dataset(SOURCE, revision=SOURCE_REVISION, split="train")
    start = time.perf_counter()
    seeds = select_seeds(rows, n=args.seeds, seed=args.sample_seed)
    examples, stats = build_examples(seeds, mutants_per_seed=args.mutants_per_seed, workers=args.workers,
                                     family=args.family)
    if args.max_per_operator:
        per_operator: Counter = Counter()
        capped = []
        for ex in examples:
            if per_operator[ex["operator"]] < args.max_per_operator:
                per_operator[ex["operator"]] += 1
                capped.append(ex)
        examples = capped
        stats["examples_after_operator_cap"] = len(examples)
    stats["operators"] = dict(sorted(Counter(ex["operator"] for ex in examples).items()))
    stats.update({"max_per_operator": args.max_per_operator, "family": args.family, "sample_seed": args.sample_seed, "seeds_selected": len(seeds), "wall_s": round(time.perf_counter() - start, 1),
                  "source": SOURCE, "revision": SOURCE_REVISION})

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("".join(json.dumps(ex) + "\n" for ex in examples))
    args.out.with_suffix(".stats.json").write_text(json.dumps(stats, indent=2))
    print(json.dumps(stats, indent=2))


if __name__ == "__main__":
    main()
