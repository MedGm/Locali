"""Read generated bugs as diffs, to judge whether they look like real mistakes.

    uv run python -m training.data.review_bugs data/v3/pilot/bugs.jsonl --per-kind 3
    uv run python -m training.data.review_bugs data/v3/pilot/rejected.jsonl --reasons
"""

import argparse
import difflib
import json
import random
from collections import Counter, defaultdict
from pathlib import Path


def show(row: dict) -> str:
    diff = difflib.unified_diff(row["fixed_code"].splitlines(), row["buggy_code"].splitlines(),
                                "correct", "with the bug", lineterm="", n=2)
    return f"== {row['source']}  [{row['kind']}]\n" + "\n".join(diff) + f"\n-> {row['error'][:200]}\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("file", type=Path)
    parser.add_argument("--per-kind", type=int, default=3)
    parser.add_argument("--kind", help="only this bug kind")
    parser.add_argument("--reasons", action="store_true", help="count rejection reasons (rejected.jsonl)")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    rows = [json.loads(line) for line in args.file.read_text().splitlines() if line.strip()]
    if args.reasons:
        for (kind, reason), n in sorted(Counter((r["kind"], r["reason"]) for r in rows).items()):
            print(f"{kind:16s} {reason:24s} {n}")
        return
    by_kind = defaultdict(list)
    for r in rows:
        if not args.kind or r["kind"] == args.kind:
            by_kind[r["kind"]].append(r)
    rng = random.Random(args.seed)
    for kind in sorted(by_kind):
        for row in rng.sample(by_kind[kind], min(args.per_kind, len(by_kind[kind]))):
            print(show(row))


if __name__ == "__main__":
    main()
