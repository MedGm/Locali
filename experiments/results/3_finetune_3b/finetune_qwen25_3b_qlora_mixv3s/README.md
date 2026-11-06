# Run E: Qwen2.5-Coder-3B + QLoRA on mixture v3s (self-distilled replay)

Same recipe, seed and data as run D (`../finetune_qwen25_3b_qlora_mixv3b_diag`), except the
general replay rows: 2,648 of the 3,587 self-oss-instruct answers (written by StarCoder2-15B) are
replaced by the base 3B's own greedy answer to the same prompt, kept when it finished, its Python
parsed and ran without error, and it shared no 13-gram with an evaluation set
(`training/kaggle/make_data/selfdistill`, `training/data/build_mix_v3s.py`; 2,944 of 3,983 answers passed
the check, 8 dropped by decontamination). The dataset has no tests, so the kept answers are not
known to be correct. Private Kaggle dataset `locali-mix-v3s` (contains Qwen2.5-Coder-3B outputs).

Question: does training on the base model's own answer style win back the HumanEval+ loss
(`../keepdoc_t4`)? `training/kaggle/train/finetune-3b-v3s`, 2026-11-02, 5.1 h, final loss 0.207 (D:
0.283; lower because the model's own answers are easier to predict). Scored locally in the
sandbox. Adapter (not in git): `~/models/adapters/qwen25-3b-qlora-mixv3s`.

## Scores, paired

| Task | n | 3B base | D | **E** | E vs D: only D / only E, p | E vs base: only base / only E, p |
|---|---|---|---|---|---|---|
| HumanEval+ | 163 | 81.0 | 72.4 | **74.8** | 5 / 9, 0.42 | 18 / 8, 0.076 |
| MBPP+ | 377 | 64.7 | 64.2 | **64.2** | 29 / 29, 1 | 18 / 16, 0.86 |
| HumanEvalFix | 164 | 46.3 | 61.6 | **63.4** | 6 / 9, 0.61 | 10 / 38, **6e-5** |
| Completion | 163 | 56.4 | 62.0 | **65.6** | 2 / 8, 0.11 | 2 / 17, **7e-4** |
| Refactoring: behaviour preserved | 163 | 86.5 | 87.7 | **87.7** | 6 / 6, 1 | 12 / 14, 0.85 |
| Test generation: bug caught | 164 | 62.2 | 82.9 | **82.3** | 5 / 4, 1 | 11 / 44, **9e-6** |
| Bug detection accuracy | 328 | 61.6 | 67.4 | **66.5** | 15 / 12, 0.70 | 20 / 36, **0.044** |
| CRUXEval-O | 800 | 42.2 | 43.4 | **43.6** | 22 / 24, 0.88 | 30 / 41, 0.24 |
| Vulnerability detection | 712 | 54.9 | 52.7 | **54.5** | 8 / 21, **0.024** | 14 / 11, 0.69 |
| Internal T1 (held-out repair) | 212 | - | 62.3 | **67.5** | 8 / 19, 0.052 | - |
| HumanEvalFix, repair format | 164 | - | 36.6 | **36.0** | 12 / 11, 1 | - |

## What it says

- **HumanEval+ moves the right way but is not won back.** E is 2.4 points above D (not
  significant) and 6.1 below the base; the loss against the base is no longer significant
  (p = 0.076, D: 0.013), but the 10 problems every fine-tuned run loses (HumanEval/54, 55, 83,
  86, 89, 97, 100, 141, 144, 154) are still all lost, with the same programs (`HumanEval/97`:
  `(a % 10) * (b % 10)` without `abs`). The replay answers were not the cause of those.
- Nothing else got worse: no task is significantly below D, and E is the best 3B run so far on
  HumanEvalFix (63.4), completion (65.6) and held-out repair (67.5, p = 0.052 vs D). The one
  significant difference is vulnerability detection, in E's favour, back to the base level.
- Since the replay is 21 % of the data and the cause is not there, what is left are the task rows
  themselves (repair, tests, review, traces), whose code targets are short programs written by
  CodeRM, Qwen3.5-9B or mutation; that is where the terse style would come from.


## Correction, 2026-11-06

The 3B base model sometimes labels its whole answer `markdown` instead of `python` (the prompt asks
for "a markdown code block"), and the scorer skipped such blocks. `evaluation/extract.py` now
counts a `markdown` block that is valid Python as code, and the affected base runs were rescored
(`samples.original.jsonl` keeps the answers, `summary.json` the previous metrics). 3B base:
HumanEvalFix 46.3 → **50.0 %** (6 of 7 such answers were correct fixes), refactoring behaviour
preserved 86.5 → **89.0 %**. The fine-tuned 3B runs never answer this way; their scores do not
change. Up-to-date paired tests: `../multiple_comparisons/README.md`. Numbers above this note are
as first written.
