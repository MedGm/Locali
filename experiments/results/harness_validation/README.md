# Harness validation

Date: 2026-09-15. Method: every official reference solution is evaluated through the same path a model answer takes (fenced-code extraction → program assembly → Docker sandbox: no network, 512 MB, 1 CPU, 128 pids). Any failure is a harness or benchmark defect, not a model error.

Datasets: `evalplus/humanevalplus@d32357c`, `evalplus/mbppplus@b2d74c9`.

## First pass (30 s timeout, all problems)

| Benchmark | Problems | Passed | Not passed |
|---|---|---|---|
| HumanEval+ | 164 | 163 | HumanEval/32 (failed) |
| MBPP+ | 378 | 376 | Mbpp/255 (crashed), Mbpp/599 (timeout) |

## Root causes (each confirmed by a controlled rerun)

| Problem | Hypothesis | Experiment | Result | Resolution |
|---|---|---|---|---|
| HumanEval/32 | The Hugging Face test is broken for every solution | Rerun reference, read error | `TypeError: Value after * must be an iterable, not float` from `_poly(*candidate(*inp), inp)` | **Excluded** |
| Mbpp/599 | Reference is O(n) with n ≈ 10⁸ and exceeds 30 s on one CPU | Rerun with 180 s timeout | Passes in 37.2 s | **Timeout raised to 60 s** for all runs |
| Mbpp/255 | Test output exceeds the memory limit | Rerun with 2 GB; compute output size of each input | Killed (exit 137) at 2 GB too; the largest input yields 1,663,740 tuples of length 77 (≈1 GiB), held twice for comparison with the reference | **Excluded**: allowing >2 GiB per sandbox is unsafe with parallel workers on a 15 GB host |

Exclusions live in `evaluation/tasks/codegen.py::EXCLUDED`, apply to every model, and are listed in each run's `summary.json`.

## Final pass (60 s timeout, exclusions applied)

| Benchmark | Problems | pass@1 of reference solutions |
|---|---|---|
| HumanEval+ | 163 | **1.000** (163/163) |
| MBPP+ | 377 | **1.000** (377/377) |

Scores in this project are therefore reported on 163 HumanEval+ and 377 MBPP+ problems. They are not directly identical to leaderboard numbers computed on 164 / 378.

## HumanEvalPack (Python), `bigcode/humanevalpack@9a41762`

| Task | Check | Result |
|---|---|---|
| humanevalfix | Canonical solution as the model's fix | **164 / 164 pass** |
| humanevalfix | Original buggy solution as the model's fix (inverse check: every item must be a real bug) | **0 / 164 pass** (161 failed, 2 timeout, 1 crashed) |
| bugdetect | Reference labels as the model's verdict (328 items: buggy + correct per problem) | accuracy, precision, recall, F1 all **1.000**; invalid rate 0 |

No exclusions needed.

## CRUXEval-O, `cruxeval-org/cruxeval@b96af04`

| Check | Result |
|---|---|
| Ground-truth output as the model's completed assertion (800 problems) | **800 / 800 pass** |

No exclusions needed.
