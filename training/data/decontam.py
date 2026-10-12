"""Training-data decontamination by word n-gram overlap with every evaluation set.

Text is reduced to lowercase word tokens (punctuation and formatting ignored), and a training
example is contaminated if it shares any n consecutive tokens (default 13, a common choice in
LLM decontamination) with any evaluation item.

    uv run python -m training.data.decontam data/t1/mutation_v1.jsonl
"""

import argparse
import json
import re
from pathlib import Path

_WORD = re.compile(r"\w+")


def tokens(text: str) -> list[str]:
    return [t.lower() for t in _WORD.findall(text)]


class NgramIndex:
    def __init__(self, n: int = 13):
        self.n = n
        self._grams: dict[int, set[str]] = {}

    def _ngrams(self, text: str):
        toks = tokens(text)
        for i in range(len(toks) - self.n + 1):
            yield hash(" ".join(toks[i : i + self.n]))

    def add(self, source: str, text: str) -> None:
        for gram in self._ngrams(text):
            self._grams.setdefault(gram, set()).add(source)

    def sources(self, text: str) -> set[str]:
        found: set[str] = set()
        for gram in self._ngrams(text):
            found |= self._grams.get(gram, set())
        return found


def evaluation_index(n: int = 13) -> NgramIndex:
    """Index over prompts, solutions and tests of every evaluation task (all items, no exclusions)."""
    from datasets import load_dataset

    from evaluation.tasks.codegen import HUMANEVAL_PLUS, MBPP_PLUS
    from evaluation.tasks.cruxeval import CRUXEVAL
    from evaluation.tasks.humanevalpack import HUMANEVALPACK
    from evaluation.tasks.security import CYBERNATIVE, SECURITYEVAL

    index = NgramIndex(n)
    for row in load_dataset(HUMANEVAL_PLUS[0], revision=HUMANEVAL_PLUS[1], split="test"):
        index.add("humaneval_plus", row["prompt"] + row["canonical_solution"])
    for row in load_dataset(MBPP_PLUS[0], revision=MBPP_PLUS[1], split="test"):
        index.add("mbpp_plus", f"{row['prompt']}\n{row['code']}")
    for row in load_dataset(HUMANEVALPACK[0], "python", revision=HUMANEVALPACK[1], split="test"):
        index.add("humanevalpack", row["prompt"] + row["canonical_solution"] + row["buggy_solution"])
    for row in load_dataset(CRUXEVAL[0], revision=CRUXEVAL[1], split="test"):
        index.add("cruxeval", row["code"])
    for row in load_dataset(SECURITYEVAL[0], revision=SECURITYEVAL[1], split="train"):
        index.add("securityeval", row["Insecure_code"])
    for row in load_dataset(CYBERNATIVE[0], revision=CYBERNATIVE[1], split="train"):
        if row["lang"].lower() == "python":
            index.add("cybernative", f"{row['chosen']}\n{row['rejected']}")
    return index


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path, help="JSONL of raw examples; writes <path>.clean.jsonl")
    parser.add_argument("--fields", nargs="+", default=["buggy_code", "fixed_code"])
    args = parser.parse_args()

    index = evaluation_index()
    examples = [json.loads(line) for line in args.path.read_text().splitlines() if line.strip()]
    kept, dropped = [], {}
    for ex in examples:
        hits = index.sources("\n".join(str(ex.get(f, "")) for f in args.fields))
        if hits:
            for h in hits:
                dropped[h] = dropped.get(h, 0) + 1
        else:
            kept.append(ex)
    out = args.path.with_suffix(".clean.jsonl")
    out.write_text("".join(json.dumps(ex) + "\n" for ex in kept))
    report = {"input": len(examples), "kept": len(kept), "dropped_by_source": dropped, "n": index.n}
    args.path.with_suffix(".decontam.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
