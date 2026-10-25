# Run B: Qwen2.5-Coder-3B + QLoRA on mixture v3

Same recipe as run A (`../finetune_qwen25_3b_qlora_mixv2`), on mixture v3: the v2 data plus 2,898
realistic bugs written by the teacher (`../v3_bugs`). `training/kaggle/finetune-3b-v3`,
2026-10-24/25: 5.8 h on one T4, final training loss 0.252. Scored on the laptop in the Docker
sandbox. All comparisons are paired exact McNemar tests on the same problems.

| Task | 3B base | A: + v2 | **B: + v3** | B vs base (lost / gained, p) | B vs A (p) |
|---|---|---|---|---|---|
| HumanEvalFix | 76 (46.3 %) | 72 (43.9 %) | **106 (64.6 %)** | 11 / 41, **4e-5** | 2 / 36, **5e-9** |
| HumanEval+ | 132 (81.0 %) | 122 (74.8 %) | 122 (74.8 %) | 18 / 8, 0.076 | 7 / 7, 1.0 |
| MBPP+ | 244 (64.7 %) | 239 | 250 (66.3 %) | 27 / 33, 0.52 | 9 / 20, 0.061 |
| CRUXEval-O | 338 (42.2 %) | 348 | 344 (43.0 %) | 34 / 40, 0.56 | 0.63 |
| Completion | 92 (56.4 %) | 102 | 100 (61.3 %) | 11 / 19, 0.20 | 0.77 |
| Test generation: bug caught | 102 (62.2 %) | 140 | 135 (82.3 %) | 12 / 45, **1e-5** | 0.23 |
| Refactoring: behaviour preserved | 141 (86.5 %) | 150 (92.0 %) | **128 (78.5 %)** | 25 / 12, **0.047** | 28 / 6, **2e-4** |

HumanEvalFix by bug type (fixed):

| Bug type | n | Base | A | B |
|---|---|---|---|---|
| Excess logic | 31 | 11 | 9 | **21** |
| Missing logic | 33 | 12 | 8 | **15** |
| Value misuse | 44 | 21 | 24 | **34** |
| Operator misuse | 25 | 15 | 14 | 17 |
| Variable misuse | 23 | 13 | 12 | 13 |
| Function misuse | 8 | 4 | 5 | 6 |

For reference on HumanEvalFix: Qwen2.5-Coder-7B (AWQ) 59.2 %, Qwen3.5-9B 65.8 %.

How the failures change (HumanEvalFix):

| | Base | A | B |
|---|---|---|---|
| Not fixed | 88 | 92 | 58 |
| of which: the buggy code returned unchanged | 31 | 50 | 15 |
| of which: a wrong fix | 55 | 41 | 42 |
| Mean output tokens | 128 | 70 | 69 |

## What it says

- **The realistic bugs are what moves repair.** Same base, same recipe, same v2 data: adding them
  takes HumanEvalFix from 43.9 to 64.6 % (36 problems gained, 2 lost), above the untrained 7B and
  close to the 9B teacher. The gain is largest exactly where the retrospective said the gap was:
  excess logic 9 → 21, missing logic 8 → 15, value misuse 24 → 34.
- **Part of it is behaviour, not knowledge.** Run A often hands the buggy code back unchanged
  (50 times); run B does so 15 times. The v2 mutation data taught "patch one token or leave it";
  the v3 bugs teach the model to make the edit a real bug needs.
- **Test generation keeps its gain** (82.3 vs 62.2 % for the base), and answers stay short (69
  tokens against the base's 128), which matters on the laptop.
- **Refactoring got worse** (78.5 %, below both the base and run A, p = 0.047 and 2e-4). The new
  repair data probably pushes the model to change behaviour when asked only to restructure code.
- **HumanEval+ stays six points below the base** in both runs (p = 0.076): a cost of the v2 data,
  not of the new bugs.

## Caveat: the prompt

Half of the new examples use the phrasing "Fix bugs in f" with the failing tests, which is how
HumanEvalFix asks. The problems and code are decontaminated, but the phrasing is shared. On
HumanEvalFix asked in our own repair format (`humanevalfix_t1fmt`), run B gains less: 34.1 vs
29.9 % for run A. Before the 64.6 % is claimed, the same problems should be asked with a paraphrased
prompt that matches neither training format, for the base, A and B.
