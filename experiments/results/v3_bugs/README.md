# v3 data: realistic bugs from the teacher

Built 2026-10-24 by `training/kaggle/bugs` (Qwen3.5-9B on 2 x T4, TP=2, temperature 0.6) from
CodeRM-UnitTest problems not used in mixtures v1/v2. Every bug was checked by the problem's own unit
tests in `evaluation/isolated.py`. The data itself is the private Kaggle dataset `locali-mix-v3`.

| | Pilot 1 (300) | Pilot 2 (150) | Full run (4,500) |
|---|---|---|---|
| Bugs kept | 142 (47 %) | 103 (69 %) | 3,271 (73 %) |
| Changing 2 or more lines | 11 % | 42 % | |
| Returned unchanged by the teacher | 105 | 5 | 154 |

Between pilot 1 and 2: missing/excess-logic bugs must remove/add a statement, up to 3 attempts per
problem, logic kinds weighted 3x/2x, the teacher states the bug in a `Bug:` line, and the stored
error is the assertion message instead of the last line of a diff.

Full run, bugs kept by kind: missing logic 745, excess logic 625, wrong update 400, wrong variable
395, wrong value 375, off by one 373, wrong condition 358. Rejections: tests still pass 372, too
many changed lines 318, no statement removed 260, unchanged 154, syntax error 39, timeout 28, no
statement added 27, signature changed 26. Kept at attempt 1/2/3: 2,268 / 677 / 326.

Mixture v3 (`build_mix_v3.py`): 13-gram decontamination dropped 51 bugs (MBPP+ 30, HumanEvalPack
21, HumanEval+ 4); 3,220 remain, split by problem into 2,898 train, 173 validation, 149 test, on top
of the unchanged v2 rows. Formats: 1,869 in the repair format with the test error, 1,351 as
"Fix bugs in f" with the failing tests.
