# Run D: Qwen2.5-Coder-3B + QLoRA on mixture v3b with corrected explanations

Same data, recipe and seed as run C (`../finetune_qwen25_3b_qlora_mixv3b`), except for the
explanation text of the 1,869 realistic-bug repair rows (T1R, repair format). In the first
upload those explanations were the teacher's own note on the bug it had made ("Changed `x` to
`y`"), 40 % cut off at 240 characters. Here each one is a reviewer's diagnosis of the buggy code
(`training/kaggle/diagnosis`: 3,138 teacher diagnoses, 133 template fallbacks). Code targets are
identical. `training/kaggle/finetune-3b-v3b-diag`, 2026-11-01, 5.1 h, final loss 0.283 (C: 0.286).

Adapter (not in git): `~/models/adapters/qwen25-3b-qlora-mixv3b-diag`.

## Scores, paired against run C on the same items

| Task | n | C | **D** | only C / only D | p |
|---|---|---|---|---|---|
| HumanEvalFix | 164 | 61.0 | **61.6** | 7 / 8 | 1 |
| Refactoring: behaviour preserved | 163 | 88.3 | **87.7** | 6 / 5 | 1 |
| Test generation: bug caught | 164 | 80.5 | **82.9** | 2 / 6 | 0.29 |
| Bug detection accuracy | 328 | 69.5 | **67.4** | 12 / 5 | 0.14 |
| HumanEval+ | 163 | 73.0 | **72.4** | 5 / 4 | 1 |
| MBPP+ | 377 | 65.5 | **64.2** | 13 / 8 | 0.38 |
| CRUXEval-O | 800 | 44.5 | **43.4** | 21 / 12 | 0.16 |
| Completion | 163 | 59.5 | **62.0** | 5 / 9 | 0.42 |
| HumanEvalFix, repair format | 164 | 35.4 | **36.6** | 12 / 14 | 0.85 |
| Internal T1 (mutations) | 212 | 66.0 | **62.3** | 21 / 13 | 0.23 |

No task differs significantly (all p > 0.14). Against the 3B base, D keeps the gains of C:
HumanEvalFix 46.3 → 61.6 (p = 3e-4), test generation 62.2 → 82.9 (p = 5e-6), refactoring
86.5 → 87.7; and the same HumanEval+ loss, 81.0 → 72.4 (p = 0.013).

## What changed: the explanations

On HumanEvalFix in the repair format (164 answers, each with a JSON diagnosis):

| | C | D |
|---|---|---|
| Explanations phrased as an edit ("Changed", "Removed", "Added", ...) | 4 | 0 |
| Median length (characters) | 276 | 289 |

Run C already wrote mostly reviewer-side explanations, since the 2,125 mutation repair rows from
v2 were written that way; the defect showed only in a few answers. This measures the form of the
explanations, not whether they are right: on `Python/0` (missing `abs()`) both runs return a
correct fix, yet both explanations blame another line (C: `distance < threshold`, D:
`idx != idx2`). Explanation accuracy was not scored.

## What it says

The fix is a cleanup, not a gain: same scores, explanations that never describe an edit. D
replaces C as the deployed model since its training data is the corrected one published on
Kaggle (locali-mix-v3b), so the deployed model and the public data match.
