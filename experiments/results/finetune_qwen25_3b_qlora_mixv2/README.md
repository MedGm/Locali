# Run A: Qwen2.5-Coder-3B + QLoRA on mixture v2

The v2 recipe (rank 16, all projections, 2 epochs, seed 3407, Unsloth 2026.10.4) and the v2 data,
on Qwen2.5-Coder-3B-Instruct@488639f instead of the 1.5B (`training/kaggle/finetune-3b-v2`,
2026-10-24). 1,770 steps in 4.6 h on one T4, final training loss 0.267. Answers generated on Kaggle
with the adapter in vLLM, scored on the laptop in the Docker sandbox. Base: the untrained 3B from
`../kaggle_coder_baselines_20261024`, same harness.

Paired exact McNemar tests, 3B base vs 3B + v2 (problems lost / gained by fine-tuning):

| Task | 3B base | 3B + v2 | Lost / gained | p |
|---|---|---|---|---|
| HumanEvalFix | 76 / 164 (46.3 %) | 72 (43.9 %) | 27 / 23 | 0.67 |
| HumanEval+ | 132 / 163 (81.0 %) | 122 (74.8 %) | 17 / 7 | 0.064 |
| MBPP+ | 244 / 377 (64.7 %) | 239 (63.4 %) | 28 / 23 | 0.58 |
| CRUXEval-O | 338 / 800 (42.2 %) | 348 (43.5 %) | 36 / 46 | 0.32 |
| Completion | 92 / 163 (56.4 %) | 102 (62.6 %) | 7 / 17 | 0.064 |
| Test generation: bug caught | 102 / 164 (62.2 %) | **140 (85.4 %)** | 9 / 47 | **3e-7** |
| Test generation: strictly valid | 27 / 164 | **118** | 4 / 95 | 1e-23 |
| Refactoring: behaviour preserved | 141 / 163 (86.5 %) | 150 (92.0 %) | 7 / 16 | 0.093 |
| Bug detection accuracy | 61.6 % | 65.9 % | | n.s. |
| Insecure generations (Bandit) | 30.6 % | 17.4 % | | |

HumanEvalFix by bug type (fixed): excess logic 11 → 9, missing logic 12 → 8, value misuse 21 → 24,
variable misuse 13 → 12, operator misuse 15 → 14, function misuse 4 → 5.

The v2 data does for the 3B what it did for the 1.5B on the skills it trains (tests, refactoring),
but it does not help repair and costs HumanEval+ a trend of six points. Missing-logic repair drops
from 12 to 8: training on single-line mutations pulls the stronger model towards one-line patches.
Run B (mixture v3, `../finetune_qwen25_3b_qlora_mixv3`) adds realistic multi-line bugs to test
whether that is what the 3B needs.
