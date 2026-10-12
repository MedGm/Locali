# Baselines on Kaggle — 4 models × 10 tasks

Generation: 2026-10-12, Kaggle 2 × T4, vLLM 0.29.0, FP16, eager mode, one model per GPU, 16 concurrent requests, greedy decoding (temperature 0), max 768 new tokens, thinking off. Job: `training/kaggle/baselines/kaggle_baselines.py` at commit `3431c53`; generation wall time 1 h 22 min for all 40 runs.
Scoring: on the laptop, in the Docker sandbox (`python -m evaluation.rescore`), at the harness commit recorded in each `summary.json` → `rescored`. Generated code never ran on Kaggle.
Energy: `nvidia-smi` board power at 1 s, integrated per run over the GPU that served the model (idle draw included).

Regenerate the tables: `uv run python experiments/scripts/baseline_table.py experiments/results/kaggle_baselines_20261012/results`

## Quality (%)

| Task | phi-4-mini | qwen2.5-coder-1.5b | qwen3.5-2b | qwen3.5-4b |
|---|---|---|---|---|
| HumanEval+ pass@1 | 71.2 | 65.0 | 47.2 | 79.8 |
| MBPP+ pass@1 | 54.1 | 56.2 | 40.8 | 66.8 |
| Completion (infilling) pass@1 | 47.9 | 35.6 | 33.7 | 54.6 |
| Bug repair (HumanEvalFix) pass@1 | 42.7 | 25.0 | 34.2 | 53.7 |
| Bug detection accuracy (chance 50) | 65.2 | 53.0 | 53.7 | 66.2 |
| Bug detection: recall | 47.6 | 88.4 | 97.6 | 98.2 |
| Bug detection: precision | 73.6 | 51.8 | 51.9 | 59.9 |
| Code reasoning (CRUXEval-O) pass@1 | 33.6 | 30.1 | 32.2 | 47.6 |
| Test generation: bugs caught | 90.2 | 46.3 | 87.2 | 97.0 |
| Test gen: generated tests correct | 69.1 | 57.7 | 74.1 | 88.9 |
| Test gen: mean coverage | 94.86 | 52.50 | 91.53 | 98.36 |
| Refactoring: behaviour preserved | 86.5 | 69.9 | 82.8 | 92.0 |
| Refactoring: improved and preserved | 33.1 | 12.3 | 22.1 | 34.4 |
| Insecure generations, Bandit (lower is better) | 21.5 | 23.1 | 15.7 | 17.4 |
| Insecure gen: unparseable answers (not scanned) | 14.1 | 0.0 | 1.7 | 0.8 |
| Vulnerability detection accuracy (chance 50, indicative) | 57.3 | 51.0 | 55.2 | 57.7 |
| Vuln detection: recall | 94.1 | 99.7 | 95.8 | 90.5 |
| Vuln detection: precision | 54.2 | 50.5 | 52.9 | 54.7 |

## Efficiency (Kaggle T4, FP16, vLLM, 16 concurrent requests)

| Measure | phi-4-mini | qwen2.5-coder-1.5b | qwen3.5-2b | qwen3.5-4b |
|---|---|---|---|---|
| Mean output tokens (all tasks) | 125 | 99 | 122 | 138 |
| Mean time to first token, s (16 concurrent) | 0.29 | 0.15 | 0.29 | 0.60 |
| Mean decode tok/s per request (16 concurrent) | 15.6 | 28.7 | 18.5 | 12.5 |
| GPU energy, kJ (all tasks) | 118 | 54 | 94 | 156 |
| GPU energy per HumanEval+ task, J | 75 | 35 | 55 | 79 |
| GPU energy per correct HumanEval+ solution, J | 105 | 54 | 116 | 98 |
| Generation wall time, min (all tasks) | 30 | 13 | 24 | 39 |

## Findings

1. **Qwen3.5-4B has the best headline score on 9 of 10 tasks** — every task except insecure generation, where Qwen3.5-2B is lowest (15.7 vs 17.4 %); its vulnerability-detection lead (57.7 vs 57.3 %) is within noise — but it cannot be fine-tuned on a T4 (W1), so it serves as the quality ceiling among the small models.
2. **Phi-4-mini is second overall** and strong where the project needs it: 90 % of bugs caught by its generated tests, 43 % bug repair, 87 % behaviour-preserving refactors. This supports decision D1 (Phi-4-mini as fine-tune #2).
3. **Qwen2.5-Coder-1.5B is the cheapest and fastest** (54 J per correct HumanEval+ solution, about half the others; 28.7 tok/s per request under load) and competitive on plain code generation, but **weakest on the fine-tuning targets**: bug repair 25 %, bugs caught by its tests 46 %, behaviour-preserving refactors 70 %. These are the T1–T3 tasks of the training data, so it has the most headroom.
4. **Detection tasks expose a "yes" bias.** The Qwen models report a bug in almost every snippet (recall 88–98 %, precision ≈ 52 %), so their accuracy is near chance (53–54 %); an always-yes model would score F1 = 66.7 %, which is why accuracy, not F1, is the headline. Phi-4-mini is conservative (recall 48 %, precision 74 %, accuracy 65 %). On the noisy vulnerability set all models are within 51–58 % accuracy. Balanced, verified labels in the T3 training data target this bias directly.
5. **Energy per correct answer ranks differently from raw cost.** Qwen3.5-4B uses 2.9× the energy of Qwen2.5-Coder over all tasks, but per correct HumanEval+ solution the gap shrinks to 1.8× (98 vs 54 J); Qwen3.5-2B is the least efficient (116 J) because it is both slower and less accurate.
6. **Precision changes individual answers but not the level.** Against the laptop Q4 runs, about 20 % of HumanEval+/MBPP+ problems flip outcome at FP16 on GPU (identical prompts, verified token-for-token), and Q4 was not worse (Qwen2.5-Coder MBPP+: 60.5 % at Q4 vs 56.2 % at FP16; paired McNemar p ≈ 0.02). Quantization comparisons therefore need the same runtime and paired tests (RQ3).

## Harness changes made while scoring these runs

Scoring is separate from generation, so each fix was applied to stored answers without regenerating; every fix was re-validated on reference answers (all 10 tasks at 100 %, see `experiments/results/harness_validation/README.md`).

| Fix | Effect on these runs |
|---|---|
| Line-based fence parser: the closing fence of a `bash`/`markdown` block no longer opens a phantom code block | Test generation only: Qwen3.5-2B bugs caught 37.8 → 87.2 %, Qwen2.5-Coder 32.3 → 46.3 %; all other tasks unchanged |
| Generated test files get `from solution import *` | Answers that omitted the import are scored on their tests |
| Assertion-level pruning of generated tests (pilot finding) | Test generation became informative (0 % strict-valid files otherwise) |

## Caveats

- One greedy sample per item; no sampling-based pass@k yet.
- Time-to-first-token and decode speed are per request with 16 concurrent requests on one T4 — server-under-load figures, not single-user latency.
- Phi-4-mini returned unparseable code for 14 % of SecurityEval prompts; unparseable answers are not scanned, which lowers its insecure rate. Bandit itself flags only 27 % of known-insecure references.
- Vulnerability-detection labels are noisy (`harness_validation`), so that row is indicative.
- HumanEval+ / MBPP+ on 163 / 377 problems after two documented exclusions.
