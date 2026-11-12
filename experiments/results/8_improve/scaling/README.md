# Run E's adapter at lower strength, and the average of runs D and E

Kaggle T4, vLLM 0.29, 2026-11-11, commit df0b806 (`training/kaggle/evaluate/scaling`). No training:
the adapter files are changed with `training/adapter_math.py` and served next to the unchanged run E
adapter, which is the control. Greedy answers, scored in the job's isolated runner.

Registered as exploratory in `docs/preregistration-runs-fg.md`: nothing here is a finding by itself.

## Control

The unchanged adapter gives run E's numbers again: HumanEvalFix 104 of 164 and MBPP+ 242 of 377
exactly, HumanEval+ 121 of 163 against 122 in the training job (one problem at the time limit).

## Results

Each variant against the control on the same problems (exact McNemar, not corrected).

| Variant | HumanEval+ (163) | HumanEvalFix (164) | MBPP+ (377) |
|---|---|---|---|
| run E, unchanged | 121 (74.2 %) | 104 (63.4 %) | 242 (64.2 %) |
| run E × 0.75 | 127 (77.9 %), 10 won / 4 lost, p = 0.18 | 103 (62.8 %), 4 / 5, p = 1 | 239 (63.4 %), 4 / 7, p = 0.55 |
| run E × 0.5 | 130 (79.8 %), 16 / 7, p = 0.09 | 95 (57.9 %), 7 / 16, p = 0.09 | 244 (64.7 %), 14 / 12, p = 0.85 |
| average of D and E | 120 (73.6 %), 5 / 6, p = 1 | 104 (63.4 %), 5 / 5, p = 1 | 248 (65.8 %), 28 / 22, p = 0.48 |

For reference, the 3B base: HumanEval+ 81 %, HumanEvalFix 50 %.

## What it shows

- The strength of the adapter moves the two scores in opposite directions, step by step: at half
  strength code writing gains 9 problems and repair loses 9. The adapter is where both the repair
  gain and the code-writing loss come from; there is no strength that keeps one and removes the other.
- At three-quarter strength repair is unchanged (103 against 104) and code writing is 6 problems
  better, which is not significant (p = 0.18). It is the only variant that meets the registered
  condition for a second step: one run on ConDefects and test generation, which were not used to
  choose it. That run is the same job with `TASKS="testgen condefects" SCALES=0.75 AVERAGE=0`.
- Averaging D and E changes nothing that can be measured. Its MBPP+ answers are much shorter
  (51 tokens against 123), as run D's are.

## Second step: run E × 0.75 on tasks not used to choose it (`step2/`)

Same job at commit eda5239 with `TASKS="testgen condefects" SCALES=0.75 AVERAGE=0`, the unchanged
adapter served next to it again; test generation scored in the laptop sandbox, 2026-11-12.

| Test generation (164) | run E, unchanged | run E × 0.75 | won / lost | p |
|---|---|---|---|---|
| planted bug caught | 136 (82.9 %) | 141 (86.0 %) | 6 / 1 | 0.125 |
| every written test passes on the correct code | 132 (80.5 %) | 119 (72.6 %) | 6 / 19 | 0.015 |

The control gives run E's test-generation score again (136 against 135 in the training job).
At three-quarter strength a few more bugs are caught, not significantly, and significantly more
answers contain a wrong test. This is not a gain: run E stays as it is.

ConDefects: the 382 answers of both adapters are in `step2/results/condefects` (18 cut off at
1,024 tokens for each). They are not scored yet: the tests are in ConDefects' `Test.zip`, which is
not on this disk. `CONDEFECTS_TESTS=<dir>/Test uv run python -m evaluation.rescore <the two folders>`.

`adapters/` (the built variants, 615 MB) is not in the repository; the job rebuilds them.

Code and text written with AI help (Claude).
