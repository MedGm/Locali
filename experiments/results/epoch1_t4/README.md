# Run D after one epoch

The adapter saved after epoch 1 of run D (`checkpoint-1041`, Kaggle dataset `locali-adapters-3b`,
folder `mixv3b-diag-ep1`), evaluated like the final adapter: `training/kaggle/plan` with
`ADAPTER=mixv3b-diag-ep1 BASE_TOO=0 TASKS="humaneval_plus mbpp_plus humanevalfix"`, vLLM 0.29.0,
T4, FP16, greedy, 2026-11-02. The checkpoint comes from the middle of a 2-epoch cosine schedule, so
it is not identical to a 1-epoch run, but it shows whether the second epoch causes the loss.

| Task | 3B base | **Epoch 1** | Run D (epoch 2) | Epoch 1 vs D, p | Epoch 1 vs base, p |
|---|---|---|---|---|---|
| HumanEval+ | 81.0 | **71.8** | 72.4 | 1 | **0.008** (22 lost / 7 gained) |
| MBPP+ | 64.7 | **63.9** | 64.2 | 1 | 0.77 |
| HumanEvalFix | 46.3 | **62.2** | 61.6 | 1 | **4e-4** (13 / 39) |

Epoch 1 already has both the repair gain and the HumanEval+ loss; the second epoch changes
neither. Shorter training is not the fix.

## Where the loss is

MBPP+ shows no loss, so it is not general forgetting of code writing. On HumanEval+ the same 10
problems are lost by all four fine-tuned runs (A to D). The fine-tuned answers drop the docstring
and its examples and write terse code that misses edge cases (`HumanEval/97`: `(a % 10) * (b % 10)`
without `abs`; `HumanEval/55`: plain recursion that times out):

| HumanEval+ answers | Keep the docstring | Pass rate, docstring kept | Pass rate, dropped |
|---|---|---|---|
| 3B base | 152 / 163 | 0.81 | 0.82 |
| Run A (v2 data) | 104 / 163 | 0.79 | 0.68 |
| Run D | 64 / 163 | 0.80 | 0.68 |

In the training data 89 % of answers with a function have no docstring (mixture v3b, train). This
is a correlation; `../plan_t4` was the first guess (answer length) and was wrong. The test of this
one is `humaneval_plus_keepdoc` (copy the signature and docstring, then write the body): `../keepdoc_t4`,
where it turns out to be a symptom, not the cause.
