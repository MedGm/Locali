**Locali fine-tuning data, version 3 of 4.** Previous: [locali-mix-v2](https://www.kaggle.com/datasets/elgorrimmohamed/locali-mix-v2). Next: [locali-mix-v3b](https://www.kaggle.com/datasets/elgorrimmohamed/locali-mix-v3b).

Project: [github.com/MedGm/Locali](https://github.com/MedGm/Locali). Generation code: `training/data/realistic_bugs.py`, `training/kaggle/bugs`; build: `training/data/build_mix_v3.py`.

## What changed from v2, and why

v2's bugs were all one-line mutations, so the model learned to patch one token. v3 keeps v2 unchanged and adds **3,220 realistic bugs (task `T1R`)**:

- problems from CodeRM-UnitTest **not used in v1/v2** (6,831 excluded), reference solution passing its tests
- the teacher (Qwen3.5-9B) is asked for **one bug of a given kind**, the kind a developer makes: missing logic, excess logic, wrong condition, off-by-one, wrong variable, wrong value, wrong update. The logic kinds get 3x and 2x the share, since that is where the model was weakest
- a bug is kept only if it parses, keeps every signature, changes at most 6 lines (and at most half of a short function), **removes a statement** (missing logic) or **adds one** (excess logic), and **the problem's own unit tests fail on it**; comments are stripped so none can point at the bug; up to 3 attempts per problem
- 4,500 problems → 3,271 bugs kept; 51 removed by 13-gram decontamination; 44 % change two or more lines (v2: none)
- two prompt formats, half each: the trained repair format with the test error (answer: one-line diagnosis + whole fixed function), and "Fix bugs in f" with the failing tests (answer: the fixed code)

| Task | Train / val / test |
|---|---|
| v2 rows (T1, T2, T3, T4, replay) | as in v2 |
| **T1R realistic bugs** | **2,898 / 173 / 149** |

## What it gave, and what went wrong

QLoRA on Qwen2.5-Coder-3B, same recipe for every run, paired on the same problems:

| HumanEvalFix, % fixed | 3B base | 3B + v2 | **3B + v3** |
|---|---|---|---|
| Benchmark prompt | 46.3 | 43.9 | **64.6** (p = 4e-5 vs base) |
| Reworded prompt no training example uses | 40.2 | 38.4 | **56.7** (p = 4e-4) |
| Up to 3 attempts with the test error | 54.9 | 52.4 | **71.3** |

The gain holds when the prompt is reworded, so it is not prompt matching; it is largest on excess logic (11 → 21 of 31) and missing logic (12 → 15 of 33). Test generation keeps v2's gain (62 → 82 % of bugs caught).

Two costs: **refactoring fell to 78.5 %** (base 86.5 %), and **HumanEval+ stayed six points below the base**. [v3b](https://www.kaggle.com/datasets/elgorrimmohamed/locali-mix-v3b) addresses them.


## Revision (25 Oct 2026)

The first upload of this version had a defect in the explanations of the realistic-bug repair examples (task `T1R`, repair format, 1,869 rows). Each explanation was the teacher's own note on the bug it had made ("Changed `x` to `y`"), so it described the edit from the wrong side, and 40 % were cut off mid-sentence at 240 characters. The teacher now rewrites each one as a reviewer's diagnosis of the buggy code (which construct is wrong, what it should do), kept only if it is complete, at most 320 characters, not phrased as an edit, and names something in the changed lines: 3,138 teacher diagnoses, 133 template fallbacks (`training/kaggle/diagnosis`). Code and all other rows are unchanged, so the models trained on the first upload were trained on the same code targets; only the explanation text differs.

## Sources and licences

As v2 for the v2 rows. T1R: problems and tests from CodeRM-UnitTest (Apache-2.0; tests generated with Llama-3.1-70B-Instruct, Llama 3.1 licence), bugs and their one-line descriptions written by Qwen3.5-9B (Apache-2.0).
