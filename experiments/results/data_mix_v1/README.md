# Locali fine-tuning mixture v1

Built 2026-10-12 by `training/data/build_mix.py` (repository github.com/MedGm/Locali). Chat-format JSONL: `{id, task, group, split, messages}`. Splits are by seed problem (`group`); no group appears in two splits.

| Task | What | Source | License |
|---|---|---|---|
| T1 | Bug repair: buggy function + failing test → JSON diagnosis + fixed function | KAKA22/CodeRM-UnitTest (single injected faults, test-verified) | Apache-2.0; unit tests in the source were generated with Llama-3.1-70B-Instruct |
| T2 | Test generation: function → compact pytest file | KAKA22/CodeRM-UnitTest suites, converted and mutation-selected | as above |
| T3 | Structured review: code → JSON findings (bug / security / quality), empty list allowed | T1 pool pairs (buggy + verified original) and bigcode/self-oss-instruct-sc2-exec-filter-50k with Bandit/Ruff labels | Apache-2.0 / ODC-BY |
| replay | General code instructions | bigcode/self-oss-instruct-sc2-exec-filter-50k | ODC-BY |

Bug explanations in T1/T3 were phrased by Qwen3.5-9B (Apache-2.0) and checked automatically; labels come only from tests and static tools. Decontaminated (13-gram) against HumanEval+, MBPP+, HumanEvalPack, CRUXEval, SecurityEval and CyberNative. Counts: see `stats.json`.
