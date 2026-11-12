# Run F: Qwen2.5-Coder-3B + QLoRA on mixture v3f (fix first, diagnosis after)

Same recipe, seed and data as run E (`../finetune_qwen25_3b_qlora_mixv3s`), except the 3,795
repair-format training rows: they ask for the complete fixed function and then the one-line JSON
diagnosis, instead of the diagnosis and then the function (`training/data/build_mix_v3f.py`,
private Kaggle dataset `locali-mix-v3f`). Same code and same diagnosis text in every row.

Question: run E fixes 104 of the 164 HumanEvalFix bugs when asked for the code only and 59 when it
has to write the diagnosis first. Is that the order of the answer? Rules written before the run:
`docs/preregistration-runs-fg.md`. `training/kaggle/train/finetune-3b-v3f`, 2026-11-11/12, commit
df0b806, 5.9 h, final loss 0.204 (E: 0.207). Scored locally in the sandbox. Adapter (not in git):
on the external drive, `runF/adapter`.

## Primary: the order matters

HumanEvalFix in the repair format, same 164 bugs (exact McNemar).

| | fixed | |
|---|---|---|
| run E, diagnosis then code (`humanevalfix_t1fmt`) | 59 | 36.0 % |
| **run F, code then diagnosis** (`humanevalfix_t1fmt_codefirst`) | **96** | **58.5 %** |

45 bugs fixed only by F, 8 only by E, **p = 2e-7**. The registered claim holds: writing the
diagnosis first costs the fix. The answers have the same length (165 tokens) in both orders.

Run F asked in the old order (diagnosis first, which it was not trained on) fixes 47.

## Secondary, F against E

| Task | n | E | F | only E / only F | p |
|---|---|---|---|---|---|
| HumanEvalFix, benchmark format | 164 | 104 | 103 | 7 / 6 | 1 |
| HumanEval+ | 163 | 122 | 121 | 2 / 1 | 1 |
| MBPP+ | 377 | 242 | 239 | 5 / 2 | 0.45 |
| Test generation: bug caught | 164 | 135 | 137 | 1 / 3 | 0.63 |
| Completion | 163 | 107 | 105 | 5 / 3 | 0.73 |
| CRUXEval-O | 800 | 349 | 351 | 13 / 15 | 0.85 |

Not registered, unpaired: bug detection 66.5 → 67.1 %, vulnerability detection 54.5 → 54.1 %,
refactoring behaviour preserved 87.7 → 87.1 % and improved 30.7 → 23.9 %, insecure code 17.4 % both.
Explaining code (the last registered secondary) has not been run for F. The internal held-out
sets are not scored here.

## What it shows

- The loss in the repair format was the order of the answer, not the format itself: with the code
  first the same data gives 96 instead of 59. Nothing else moves.
- The fix with a diagnosis in one answer (96) is still below the fix alone (103 for F, 104 for E).
  The assistant already asks for the fix alone and for the explanation afterwards
  (`backend/agents/debug.py`), so it gains nothing from run F, and run E stays the default. Run F
  would be the model to use where one call must return both.

Code and text written with AI help (Claude).
