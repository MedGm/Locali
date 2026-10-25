# Run C: Qwen2.5-Coder-3B + QLoRA on mixture v3b

Run B (`../finetune_qwen25_3b_qlora_mixv3`) left two costs: refactoring 78.5 % (base 86.5 %) and
HumanEval+ six points below the base. Mixture v3b keeps the 2,898 realistic bugs, keeps half of the
v2 mutation repair rows (2,125 instead of 4,323) and doubles the general replay set (3,587 rows
of self-oss-instruct): 16,645 training rows (`build_mix_v3.py --t1-keep 0.5 --replay-total 4000`).
Same recipe; `training/kaggle/finetune-3b-v3b`, 2026-10-25, 4.9 h, final loss 0.286.

| Task | 3B base | B: v3 | **C: v3b** | C vs base (lost / gained, p) | C vs B (p) |
|---|---|---|---|---|---|
| HumanEvalFix | 76 (46.3 %) | 106 (64.6 %) | **100 (61.0 %)** | 14 / 38, **0.001** | 14 / 8, 0.29 |
| Refactoring: behaviour preserved | 141 (86.5 %) | 128 (78.5 %) | **144 (88.3 %)** | 13 / 16, 0.71 | 3 / 19, **9e-4** |
| Test generation: bug caught | 102 (62.2 %) | 135 (82.3 %) | **132 (80.5 %)** | 14 / 44, **1e-4** | 0.51 |
| CRUXEval-O | 338 (42.2 %) | 344 (43.0 %) | 356 (44.5 %) | 33 / 51, 0.063 | 0.073 |
| MBPP+ | 244 (64.7 %) | 250 (66.3 %) | 247 (65.5 %) | 0.79 | 0.69 |
| Completion | 92 (56.4 %) | 100 (61.3 %) | 97 (59.5 %) | 0.40 | 0.63 |
| HumanEval+ | 132 (81.0 %) | 122 (74.8 %) | **119 (73.0 %)** | 19 / 6, **0.015** | 0.61 |
| Bug detection accuracy | 61.6 % | 63.1 % | 69.5 % | | |

HumanEvalFix by bug type (fixed, base / B / C): excess logic 11 / 21 / 16, missing logic 12 / 15 / 14,
value misuse 21 / 34 / 36, operator misuse 15 / 17 / 18, variable misuse 13 / 13 / 11,
function misuse 4 / 6 / 5.

## What it says

- **Refactoring is fixed** (88.3 %, back to the base level and 16 problems above run B) and repair
  keeps most of its gain (61.0 %, +14.7 over the base; 3.6 below B, not significant). Test
  generation keeps its gain, and bug detection is the best of all runs (69.5 %).
- **HumanEval+ did not recover**, so the mutation bugs were not its cause. The 19 problems lost
  are wrong solutions, not format failures. A likely cause: the base explains before coding (242
  output tokens on HumanEval+), every fine-tuned run answers with bare code (88 tokens). Shorter
  answers save time and energy on the laptop but may cost the reasoning the base did in its
  explanation. This is a hypothesis; it would need a run whose targets keep a short plan before
  the code.
- **Run C is the better model to deploy**: the same repair class as B without the refactoring
  regression, at the cost of HumanEval+ (73.0 vs 81.0 % for the base).
