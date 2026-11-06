# Does a plan before the code win back HumanEval+?

Every fine-tuned 3B run scores 6-9 points below the base on HumanEval+. The guess was that the
fine-tuned models answer with bare code (about 90 output tokens) while the base explains (about
240), and lose the reasoning in that explanation. Test: ask both for a short plan before the code
(`humaneval_plus_plan`, evaluation/tasks/codegen.py), same problems, same server, greedy.
`training/kaggle/evaluate/plan`, vLLM 0.29.0 on a T4, FP16, run D adapter, 2026-11-02.

| HumanEval+ (163 problems) | Standard prompt | Plan first | only standard / only plan | p | Output tokens |
|---|---|---|---|---|---|
| 3B base | 132 (81.0 %) | 129 (79.1 %) | 14 / 11 | 0.69 | 242 → 475 |
| 3B run D | 117 (71.8 %) | 114 (69.9 %) | 20 / 17 | 0.74 | 96 → 166 |

Both models follow the instruction (all 163 answers start with a plan), and neither gains.

## What it says

- **The guess is wrong.** The base's 240 tokens are not reasoning before the code: with the
  standard prompt all 163 of its answers start with the code block and explain afterwards. Asking
  for the plan first does not help the base either.
- Run D loses 22 problems the base solves and gains 7 (p = 0.008). Of the 22, 20 fail the tests
  and 2 time out: wrong programs, not format. Fine-tuning made code writing from a description
  slightly worse (forgetting), which a prompt does not undo.
- Next test: the checkpoint after epoch 1 of run D (less training, possibly less forgetting).
