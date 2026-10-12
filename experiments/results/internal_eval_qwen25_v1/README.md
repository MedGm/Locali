# In-distribution evaluation — Qwen2.5-Coder-1.5B base vs QLoRA v1

Items: the held-out test split of mixture v1 (problems never seen in training): 164 T1, 134 T2, 164 T3. Prompts are the exact training prompts. Generation: Kaggle, base on GPU 0 and base + adapter on GPU 1 in the same session (vLLM, FP16, greedy, 16 concurrent). Scoring: local sandbox. Reference answers validate at 100 % on all three tasks (`../harness_validation/README.md`).

## Paired comparison (exact McNemar; * = p < 0.05)

| Task | n | qwen2.5-coder-1.5b | qwen2.5-coder-1.5b-ft-qlora | Δ (points) | only A | only B | McNemar p |
|---|---|---|---|---|---|---|---|
| internal_t1 | 164 | 1.8 | 72.0 | +70.1 * | 0 | 115 | 4.81e-35 |
| internal_t2 | 134 | 11.9 | 21.6 | +9.7 * | 5 | 18 | 0.0106 |
| internal_t3 | 164 | 23.8 | 53.0 | +29.3 * | 16 | 64 | 5.87e-08 |

Per-item outcome: internal_t1 = fixed code passes the problem's full original suite; internal_t2 = every injected fault caught; internal_t3 = buggy item has a bug finding on the injected line / clean item has no bug finding / tool item reports all tool-flagged lines.

## Detailed metrics

| Task | Metric | Base | Fine-tuned |
|---|---|---|---|
| T1 repair | passes full suite | 1.8 % | **72.0 %** |
| | exact fix (same AST as original) | 1.8 % | 70.1 % |
| | bug line located | 0.0 % | 79.9 % |
| | parseable diagnosis | 90.9 % | 100 % |
| T2 tests | at least one valid test | 51.5 % | 68.7 % |
| | generated tests correct | 29.9 % | 40.2 % |
| | injected faults caught | 19.4 % | **37.3 %** |
| T3 review | bug found on the injected line | 6.3 % | **57.8 %** |
| | clean code: no false bug | 39.1 % | 59.4 % |
| | tool-flagged lines recalled | 33.9 % | 45.8 % |
| | parseable answer | 95.1 % | 100 % |

## Findings

1. **The trained skills were learned.** Repair in the T1 format goes from 1.8 to 72.0 %. The base model's low score is partly format — only 23 of 164 base answers contained a fixed function — but among those 23 it passes 3 (13 %), against 118 of 164 (72 %) after fine-tuning.
2. **Benchmark gaps are a transfer problem, not a learning failure.** The same model gains only +4.9 (n.s.) on HumanEvalFix and nothing on HumanEvalPack bug detection, which use different prompts and human-written bugs. Next step: score the benchmarks also in the trained formats (same items, T1/T3 prompts) to separate format from bug distribution.
3. **Review still over-reports bugs.** On clean code 40.6 % of answers still claim a bug (base: 60.9 %); the contrastive pairs helped but did not remove the bias.
4. **Test generation on competition-style functions stays hard** (37 % of injected faults caught) even though the HumanEvalPack benchmark rose to 83.5 %: CodeRM functions have no docstring, so the expected values are harder to derive.
