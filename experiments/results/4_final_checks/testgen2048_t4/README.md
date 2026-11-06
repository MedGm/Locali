# Test generation with 2,048 output tokens (pre-registered check, part 2)

Protocol: `docs/preregistration-repair.md`, part 2, registered in commit 15aa6b9 (2026-11-05
14:56) before this run. Job: `training/kaggle/evaluate/testgen2048` at commit cc1a73c (after the registration);
Kaggle 2 x T4, vLLM 0.29, greedy, generation_config defaults; scored in the local Docker
sandbox with `evaluation.rescore` (60 s per suite on the correct and on the buggy code).

## Why

At 768 tokens the 3B base was cut off on 100 of 164 answers and kept no test on 55 problems, so the
reported gain (62 → 83 % of bugs caught) could have come from the budget.

## Result

| 164 problems | 3B base | Run D | Run E | 1.5B base | 1.5B QLoRA v2 |
|---|---|---|---|---|---|
| Answers cut off at 2,048 tokens | 97 | 1 | 3 | 46 | 5 |
| Mean output tokens | 1,340 | 119 | 137 | 788 | 169 |
| Problems with at least one kept test | 106 | 159 | 159 | 129 | 158 |
| **Bugs caught** | **99** | **136** | **135** | **75** | **135** |
| Bugs caught among problems with a kept test | 93.4 % | 85.5 % | 84.9 % | 58.1 % | 85.4 % |
| Catches that were a timeout | 1 | 1 | 1 | 0 | 0 |

At 768 tokens (earlier runs): base 102 caught, cut off 100; run D 136, cut off 1.

| Comparison | base only / fine-tune only | p (exact McNemar) | Holm p |
|---|---|---|---|
| **Primary: run D vs 3B base** | 11 / 48 | 1.2e-06 | (one test) |
| Run E vs 3B base | 12 / 48 | 3.2e-06 | 3.2e-06 |
| 1.5B QLoRA v2 vs 1.5B base | 8 / 68 | 5.6e-13 | 1.1e-12 |

## Outcome, as registered

**D better, p < 0.05.** The registered sentence was: "With a budget large enough for the base, the
fine-tune still catches more bugs." Its premise did not hold, so it is written as follows instead:

> With 2,048 tokens instead of 768 the fine-tune still catches more bugs (136 vs 99 of 164,
> p = 1e-6), but the extra budget did not let the base finish: it was cut off on 97 answers instead
> of 100. The base does not stop writing tests (often near-identical asserts, in 25 answers a pure
> repetition loop), and a file cut off in the middle keeps no test on 44 problems. The gain is that
> the fine-tune writes short, complete test files. Where the base does keep tests, they catch the
> bug more often (93 vs 86 %).

So the test-generation gain is real and does not come from the 768-token limit, but it is a gain in
finishing a usable test file, not in writing stronger tests.

## How "looping" was counted

An answer cut off at the limit counts as a repetition loop when its last 600 characters compress
to under 15 % of their size with zlib (the same few characters over and over). That is a narrow
definition, decided after reading the answers: the other cut-off answers keep adding new but
near-identical asserts, which this check does not catch.

## Files

- `results/<model>/`: `samples.jsonl` (answers and scores; `samples.original.jsonl` before
  scoring), `summary.json`.
- `logs/`, `*.log`: Kaggle and vLLM logs.

Code and text written with AI help (Claude); every figure above comes from the files listed here.
