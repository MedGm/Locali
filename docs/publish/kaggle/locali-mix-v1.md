**Locali fine-tuning data, version 1 of 4.** Next: [locali-mix-v2](https://www.kaggle.com/datasets/elgorrimmohamed/locali-mix-v2).

Locali is a software-engineering assistant that runs on a laptop with a small model (Qwen2.5-Coder 1.5B / 3B). This dataset is the first mixture used to fine-tune it with QLoRA. Code, training jobs, evaluation and every result: [github.com/MedGm/Locali](https://github.com/MedGm/Locali).

## Why this data

The baselines showed that Qwen2.5-Coder-1.5B was the cheapest model per correct answer but the weakest on the assistant's own tasks: it fixed 25 % of HumanEvalFix, its generated tests caught 46 % of bugs, and it reported a bug in almost every snippet. The mixture targets exactly those tasks, with labels that come from execution and tools, not from a model's opinion.

## Contents (chat JSONL: `id`, `task`, `group`, `messages`)

| Task | Train / val / test | What the model learns | How it is built and checked |
|---|---|---|---|
| T1 repair | 3,384 / 197 / 164 | buggy function + failing test → one-line JSON diagnosis + whole fixed function | one fault injected by mutation (comparison, boolean, arithmetic, off-by-one, negated condition) into a solution that passes its tests; kept only if a real test fails |
| T2 tests | 2,619 / 148 / 134 | function → compact pytest file | from CodeRM-UnitTest suites, converted and kept when they pass on the solution and fail on mutants |
| T3 review | 2,588 / 125 / 164 | code → JSON list of findings (bug / security / quality), possibly empty | bug/clean pairs from the T1 pool, plus self-oss code labelled by Bandit and Ruff |
| replay | 1,794 / 86 / 113 | general code instructions | self-oss-instruct, against forgetting |

Splits are by source problem: a problem never appears in two splits. All rows are 13-gram decontaminated against HumanEval+, MBPP+, HumanEvalPack, CRUXEval, SecurityEval and CyberNative. Bug explanations were phrased by Qwen3.5-9B and accepted only if they named the changed line; otherwise a template is used.

## What it gave, and what went wrong

QLoRA on Qwen2.5-Coder-1.5B, paired against the base model on the same problems:

- test generation, bugs caught: 46.3 → 83.5 % (p = 2e-12); behaviour-preserving refactoring 69.9 → 92.6 %
- HumanEvalFix +4.9 points, not significant: gains only on bug types that look like the injected faults
- **code reasoning (CRUXEval-O) fell 30.1 → 25.5 % (p = 0.0005)**: forgetting
- 40.6 % false bug reports on clean code in the internal review test

Those three problems are what [version 2](https://www.kaggle.com/datasets/elgorrimmohamed/locali-mix-v2) addresses.

## Sources and licences

- [KAKA22/CodeRM-UnitTest](https://huggingface.co/datasets/KAKA22/CodeRM-UnitTest), Apache-2.0 (its unit tests were generated with Llama-3.1-70B-Instruct; the Llama 3.1 licence applies to them)
- [bigcode/self-oss-instruct-sc2-exec-filter-50k](https://huggingface.co/datasets/bigcode/self-oss-instruct-sc2-exec-filter-50k), ODC-BY
- explanations written by Qwen3.5-9B (Apache-2.0)
