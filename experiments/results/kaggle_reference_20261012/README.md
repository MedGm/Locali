# Reference baseline — Qwen3.5-9B (the "larger general-purpose LLM")

Generation: 2026-10-12, Kaggle 2 × T4, vLLM 0.29.0, FP16, **tensor parallel over both GPUs**, eager mode, 16 concurrent requests, greedy, max 768 tokens, thinking off — otherwise identical to the four-model run (`../kaggle_baselines_20261012/`). Scored locally in the Docker sandbox. Generation wall time 61 min for all 10 tasks.

Regenerate: `uv run python experiments/scripts/baseline_table.py experiments/results/kaggle_baselines_20261012/results experiments/results/kaggle_reference_20261012/results`

## Quality (%)

| Task | phi-4-mini | qwen2.5-coder-1.5b | qwen3.5-2b | qwen3.5-4b | qwen3.5-9b |
|---|---|---|---|---|---|
| HumanEval+ pass@1 | 71.2 | 65.0 | 47.2 | 79.8 | 84.0 |
| MBPP+ pass@1 | 54.1 | 56.2 | 40.8 | 66.8 | 62.1 |
| Completion (infilling) pass@1 | 47.9 | 35.6 | 33.7 | 54.6 | 62.0 |
| Bug repair (HumanEvalFix) pass@1 | 42.7 | 25.0 | 34.2 | 53.7 | 65.8 |
| Bug detection accuracy (chance 50) | 65.2 | 53.0 | 53.7 | 66.2 | 72.0 |
| Bug detection: recall | 47.6 | 88.4 | 97.6 | 98.2 | 97.0 |
| Bug detection: precision | 73.6 | 51.8 | 51.9 | 59.9 | 64.6 |
| Code reasoning (CRUXEval-O) pass@1 | 33.6 | 30.1 | 32.2 | 47.6 | 54.5 |
| Test generation: bugs caught | 90.2 | 46.3 | 87.2 | 97.0 | 95.7 |
| Test gen: generated tests correct | 69.1 | 57.7 | 74.1 | 88.9 | 91.1 |
| Test gen: mean coverage | 94.86 | 52.50 | 91.53 | 98.36 | 97.80 |
| Refactoring: behaviour preserved | 86.5 | 69.9 | 82.8 | 92.0 | 92.6 |
| Refactoring: improved and preserved | 33.1 | 12.3 | 22.1 | 34.4 | 36.2 |
| Insecure generations, Bandit (lower is better) | 21.5 | 23.1 | 15.7 | 17.4 | 24.0 |
| Insecure gen: unparseable answers (not scanned) | 14.1 | 0.0 | 1.7 | 0.8 | 1.7 |
| Vulnerability detection accuracy (chance 50, indicative) | 57.3 | 51.0 | 55.2 | 57.7 | 61.9 |
| Vuln detection: recall | 94.1 | 99.7 | 95.8 | 90.5 | 87.6 |
| Vuln detection: precision | 54.2 | 50.5 | 52.9 | 54.7 | 57.9 |

## Efficiency (Kaggle T4, FP16, vLLM, 16 concurrent requests)

| Measure | phi-4-mini | qwen2.5-coder-1.5b | qwen3.5-2b | qwen3.5-4b | qwen3.5-9b |
|---|---|---|---|---|---|
| Mean output tokens (all tasks) | 125 | 99 | 122 | 138 | 142 |
| Mean time to first token, s (16 concurrent) | 0.29 | 0.15 | 0.29 | 0.60 | 0.62 |
| Mean decode tok/s per request (16 concurrent) | 15.6 | 28.7 | 18.5 | 12.5 | 8.6 |
| GPU energy, kJ (all tasks) | 118 | 54 | 94 | 156 | 478 |
| GPU energy per HumanEval+ task, J | 75 | 35 | 55 | 79 | 354 |
| GPU energy per correct HumanEval+ solution, J | 105 | 54 | 116 | 98 | 421 |
| Generation wall time, min (all tasks) | 30 | 13 | 24 | 39 | 60 |

## Findings

1. **9B leads on 7 of 10 tasks**, but the 4B model is ahead on MBPP+ (66.8 vs 62.1 %), level on test generation (bugs caught 97.0 vs 95.7 %), and 9B produces the most Bandit-flagged code of all five models (24.0 %).
2. **Cost grows much faster than quality.** Over all tasks 9B uses 478 kJ — 3.1× Qwen3.5-4B and 8.9× Qwen2.5-Coder-1.5B. Per correct HumanEval+ solution: 421 J (9B) vs 98 J (4B) vs 54 J (Qwen2.5-Coder). On HumanEval+ the 4B model reaches 79.8 % against 84.0 % for 9B at about a quarter of the energy per correct solution.
3. For the project's thesis, this is the reference point: small models give up a few points on most tasks for a several-fold reduction in energy, memory (9B does not fit one T4 in FP16) and latency (8.6 vs 28.7 tok/s per request against Qwen2.5-Coder).

## Caveats

- 9B needs both T4s (19.3 GB of FP16 weights); its energy covers two boards and includes tensor-parallel communication, while the small models used one board each.
- Same scoring caveats as the four-model run (one greedy sample; detection labels noisy for vulnerabilities; Bandit recall 27 %).
