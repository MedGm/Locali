---
license: other
license_name: mixed-apache-2.0-odc-by-llama3.1
language: [en]
tags: [code, python, bug-repair, test-generation, code-review, built-with-llama]
size_categories: [10K<n<100K]
configs:
  - config_name: default
    data_files:
      - {split: train, path: train.jsonl}
      - {split: validation, path: val.jsonl}
      - {split: test, path: test.jsonl}
---

# locali-mix-v2

The fine-tuning mixture behind the [Locali adapters](https://huggingface.co/MedGm/Llama-Locali-Qwen2.5-Coder-1.5B-QLoRA).
Chat-format JSONL, one example per line: `{id, task, group, split, messages}`.

| Task | What the model sees → what it answers | Train | Val | Test |
|---|---|---|---|---|
| T1 | buggy function + failing test + error → JSON diagnosis + fixed function | 4,323 | 252 | 212 |
| T2 | function → compact pytest file | 2,619 | 148 | 134 |
| T3 | code → JSON list of findings (bug / security / quality), possibly empty | 3,641 | 185 | 229 |
| T4 | function + call → the exact return value | 1,775 | 81 | 96 |
| replay | general coding instructions | 1,794 | 86 | 113 |

## How it was made

- **Seed problems** come from [KAKA22/CodeRM-UnitTest](https://huggingface.co/datasets/KAKA22/CodeRM-UnitTest):
  short Python functions that pass their own unit tests.
- **T1 bugs** are single-line edits: wrong comparison or arithmetic operator, off-by-one constant,
  swapped variable, dropped condition, swapped function, and similar. An edit is kept only if a
  real test fails in a sandbox. The failing test and its actual error message go into the prompt.
  Qwen3.5-9B wrote the one-sentence explanations; each was checked automatically against the known
  fault, with a template used when the check failed. A quarter of the problems are used as T3
  review pairs (buggy version and fixed version) instead.
- **T2** answers are the problems' own tests, converted to pytest. They were picked so they catch
  injected faults.
- **T3** labels come from tests (the injected bug) and from Ruff and Bandit (quality and security
  findings), never from a model. There are 500 extra reviews of test-verified correct functions with
  no bug finding.
- **T4** calls are taken from each problem's tests. The value was traced in a sandbox and kept only
  if it matches what the test expects.
- **Replay** rows come from [bigcode/self-oss-instruct-sc2-exec-filter-50k](https://huggingface.co/datasets/bigcode/self-oss-instruct-sc2-exec-filter-50k).

Splits are by seed problem, so all examples built from one problem land in the same split.
Everything was checked for 13-gram overlap with HumanEval+, MBPP+, HumanEvalPack, CRUXEval,
SecurityEval and CyberNative's vulnerability set, and overlapping rows were removed.

Version 1 of the mixture is the subset without T4, without the second family of bug operators and
without the 500 extra clean reviews. Every v1 row is in v2 unchanged and in the same split.

Builder code: `training/data/` in the [project repository](https://github.com/MedGm/Locali).

## Licences and attribution

- CodeRM-UnitTest: Apache-2.0. Its unit tests were generated with Llama-3.1-70B-Instruct, so the
  [Llama 3.1 Community License](https://www.llama.com/llama3_1/license/) applies to that part.
  Models trained on this data should start their name with "Llama". Built with Llama.
- self-oss-instruct-sc2-exec-filter-50k: ODC-BY.
- Explanations by Qwen3.5-9B: Apache-2.0.
