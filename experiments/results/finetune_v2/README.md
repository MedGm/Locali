# Fine-tuning on mixture v2: QLoRA, 16-bit LoRA, rsLoRA (Qwen2.5-Coder-1.5B)

Date: 2026-10-13. Data: [mixture v2](../data_mix_v2/README.md). It is a superset of v1 and adds T4 execution traces, bugs from new mutation operators, and verified clean reviews. Phi-4-mini QLoRA on the same data is reported in [finetune_phi4mini_qlora_v2](../finetune_phi4mini_qlora_v2/README.md) once it finishes.

Per-run folders hold samples, scores, logs, GPU power and `train_report.json`: [qlora](../finetune_qwen25_qlora_v2/), [lora16](../finetune_qwen25_lora16_v2/), [rslora](../finetune_qwen25_rslora_v2/). The base and v1 answers on the v2 internal test split come from one extra evalgen job, in [internal_eval_v2split](../internal_eval_v2split/).

## Setup

All three runs share the same pipeline as v1 (`training/kaggle/finetune/finetune_job.py`, code at commit `371ff29`):
- **Training:** one T4, r = 16, α = 16, all projections, 2 epochs, lr 2e-4 cosine, effective batch 16, seed 3407, loss on the completion only. The only difference between runs is `METHOD`.
- **Answers:** generated with vLLM FP16 serving base + adapter, greedy decoding.
- **Scoring:** done locally in the Docker sandbox.
- **Pairing:** benchmarks pair with the FP16 Kaggle baselines and the v1 runs.

| Run | Base weights | Train time | Final train loss | Peak GPU memory |
|---|---|---|---|---|
| QLoRA | NF4 | 2 h 04 min | 0.291 | 3.09 GB |
| 16-bit LoRA | FP16 | 2 h 17 min | 0.286 | 4.85 GB |
| rsLoRA (QLoRA + rank-stabilised scaling) | NF4 | 2 h 34 min | 0.269 | 3.09 GB |

14,151 training examples (one dropped for exceeding 2,048 tokens). Train times are not a controlled speed comparison: the runs used different Kaggle machines, two at a time.

## Benchmarks: base vs each v2 run

Pass rate or accuracy in %, with the exact McNemar p-value on paired items in brackets.

| Task | n | Base | v1 | QLoRA v2 | 16-bit v2 | rsLoRA v2 |
|---|---|---|---|---|---|---|
| HumanEval+ | 163 | 65.0 | 65.0 | 62.0 (0.51) | 65.6 (1) | 62.0 (0.52) |
| MBPP+ | 377 | 56.2 | 58.9 | **62.1 (0.005)** | 57.0 (0.80) | 60.2 (0.063) |
| Completion (infilling) | 163 | 35.6 | 34.4 | 36.8 (0.84) | **41.7 (0.041)** | 37.4 (0.63) |
| HumanEvalFix | 164 | 25.0 | 29.9 | **36.0 (0.006)** | **37.2 (0.002)** | 31.7 (0.12) |
| CRUXEval-O | 800 | 30.1 | *25.5* | 28.7 (0.31) | 28.1 (0.13) | 31.1 (0.46) |
| Refactor (behaviour preserved) | 163 | 69.9 | 92.6 | **93.9 (9e-10)** | **92.6 (9e-9)** | **93.9 (9e-10)** |
| Testgen (bug caught) | 164 | 46.3 | 83.5 | **82.3 (2e-12)** | **81.1 (8e-12)** | **85.4 (5e-14)** |
| Bug detection (accuracy) | 328 | 53.0 | 54.9 | **65.5 (0.0004)** | 53.4 (1) | 56.1 (0.099) |
| Vulnerability detection | 712 | 51.0 | 50.4 | 51.5 (0.54) | 50.3 (0.23) | 50.7 (0.75) |
| Secure codegen (not flagged) | 121 | 76.9 | 81.8 | 81.0 (0.13) | 81.8 (0.070) | **82.6 (0.016)** |
| HumanEvalFix, T1 format | 164 | 9.1 | 17.7 | **24.4 (4e-5)** | **19.5 (0.003)** | **23.2 (7e-5)** |
| Bug detection, T3 format | 328 | 49.7 | 60.4 | **65.9 (8e-6)** | **65.2 (4e-5)** | **65.2 (2e-5)** |

Bold means p < 0.05. *v1's CRUXEval-O was significantly below base (p = 0.0005).*

## v1 → v2 (QLoRA, same recipe, only the data changed)

| Task | v1 | v2 | only v1 | only v2 | p |
|---|---|---|---|---|---|
| CRUXEval-O | 25.5 | 28.7 | 23 | 49 | **0.003** |
| HumanEvalFix | 29.9 | 36.0 | 3 | 13 | **0.021** |
| Bug detection | 54.9 | 65.5 | 48 | 83 | **0.003** |
| MBPP+ | 58.9 | 62.1 | 7 | 19 | **0.029** |
| Bug detection, T3 format | 60.4 | 65.9 | 8 | 26 | **0.003** |
| HumanEvalFix, T1 format | 17.7 | 24.4 | 8 | 19 | 0.052 |
| all other benchmarks | | | | | n.s. (none worse) |

## In-distribution: held-out problems of the v2 test split

| Task | n | Base | v1 | QLoRA v2 | 16-bit v2 | rsLoRA v2 |
|---|---|---|---|---|---|---|
| T1 repair (all) | 212 | 2.4 | 59.0 | 63.7 | 63.7 | 67.0 |
| … v1-operator bugs | 164 | 1.8 | 72.0 | 72.6 | 70.7 | 76.8 |
| … new v2-operator bugs | 48 | 4.2 | 14.6 | **33.3** | **39.6** | **33.3** |
| T2 tests (all faults caught) | 134 | 11.2 | 21.6 | 23.9 | 25.4 | 25.4 |
| T3 review (item correct) | 229 | 26.2 | 52.0 | 50.7 | **63.8** | 57.6 |
| T4 trace (exact value) | 96 | 42.7 | *28.1* | **51.0** | **52.1** | **52.1** |

Every v2 run beats base on every internal task (p ≤ 0.04). v1 → QLoRA v2: T4 28.1 → 51.0 (p = 5e-7) and new bug types 14.6 → 33.3 (p = 0.022). On v1's own test items T1/T2/T3 are unchanged (p ≥ 0.25). v1 reproduces exactly: 72.0 on its own items, as in the [first internal evaluation](../internal_eval_qwen25_v1/README.md).

## What is robust and what is not

**Robust: holds in all three variants, mostly p < 1e-4, survives any multiple-comparison correction.**
- Test generation (+35–39 points) and behaviour-preserving refactoring (+23–24 points).
- Repair and detection asked in the trained formats (+10–15 points).
- All in-distribution tasks.
- The CRUXEval-O forgetting of v1 is gone: no v2 run differs from base, against −4.6 points for v1. The T4 trace data is the only change aimed at it, and the in-distribution trace score rose 28 → 51.
- The new bug types are learned (14.6 → 33–40 %), though they stay much harder than v1-style faults (~72 %).

**Not robust (one variant only, p between 0.005 and 0.05):**
- **Bug detection +12.5 (QLoRA v2 only).** QLoRA v2 answers "has a bug" on 48 % of items: recall 0.64, specificity 0.67, balanced accuracy 0.655. The other two runs keep the yes-bias of base and v1, saying "has a bug" on 89–93 % of items (balanced accuracy 0.53–0.56). The data is identical, so this looks like run-to-run variability in the decision threshold, not an effect of the data. A second seed is needed before claiming it.
- MBPP+ (QLoRA only), completion (16-bit only), secure codegen (rsLoRA only): single-run effects near p = 0.05.
- HumanEvalFix: +11–12 for QLoRA and 16-bit LoRA (p ≤ 0.006), +6.7 for rsLoRA (p = 0.12). Likely real, but its size is uncertain.

**Did not work:** the 500 verified clean reviews did not reduce false bug reports on clean twins. QLoRA v2 got 34/64 right against 38/64 for v1 on the shared items.

**Unchanged everywhere:** HumanEval+, vulnerability detection (~50 %, chance level for every model so far).

## QLoRA vs 16-bit LoRA vs rsLoRA

Paired against QLoRA v2, the only significant differences are:
- **16-bit LoRA:** T3 review +13.1 (p = 5e-6), bug detection −12.2 (p = 0.001, the threshold effect above), MBPP+ −5.0 (p = 0.0009).
- **rsLoRA:** CRUXEval-O +2.4 (p = 0.027), T3 review +7.0 (p = 0.020), bug detection −9.5 (p = 0.009).

Every other task differs by less than the noise. **Quantizing the frozen base to NF4 during training costs nothing measurable on these tasks** and saves 36 % of peak memory (3.09 vs 4.85 GB). rsLoRA, at the same rank (r = 16), does not change the picture. Its scaling (α/√r instead of α/r) mainly matters at higher ranks, which were not tested.

Decision for the next steps (quantization ladder, platform): **QLoRA v2** is the reference adapter. It is the cheapest to train and never significantly worse than base. It trails rsLoRA on CRUXEval-O (−2.4 points) and both other variants on in-distribution review (T3). It leads on bug detection and MBPP+, but the bug-detection lead is the unreplicated threshold effect described above. None of these differences is large enough to justify a costlier recipe.

## Caveats

- One seed per configuration. The bug-detection result shows that single-run differences of ~10 points on a threshold-sensitive task can arise without any change in data or method.
- Rerunning the base model on the same items with vLLM is not bitwise deterministic. Base internal T2 was 11.9 % in the v1 evaluation and 11.2 % here, on the same 134 items.
- Base and v1 benchmark answers come from earlier jobs on the same runtime (vLLM 0.29.0, T4, FP16, greedy).
- Efficiency numbers are not compared: adapters are served unmerged (LoRA in vLLM). Merged-model latency and energy belong to the quantization ladder.
