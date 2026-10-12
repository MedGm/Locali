# Format vs bug-type transfer check — QLoRA v1 (Qwen2.5-Coder-1.5B)

Date: 2026-10-13. Commit `01c5b94`. Kaggle job `locali-evalgen` v2: base model on GPU 0 and base + adapter on GPU 1, vLLM FP16 eager, greedy decoding, generate-only. All scoring was done locally in the Docker sandbox. GPU time: 11 min.

## Question

QLoRA v1 improved strongly on held-out *training-style* problems: T1 repair went from 1.8 % to 72.0 % ([internal evaluation](../internal_eval_qwen25_v1/README.md)). On HumanEvalFix (+4.9, p = 0.27) and HumanEvalPack bug detection (+1.8, p = 0.38) the change was not significant. Two explanations are possible:

1. **Format.** The benchmark prompts differ from the trained prompts, so the learned behaviour is not triggered.
2. **Bug type.** Human-written bugs differ from the injected single-token faults the model was trained on.

## Method

The same HumanEvalPack items are asked in the trained prompt formats (`evaluation/tasks/format_transfer.py`). Task ids match the original tasks, so outcomes pair item by item across formats.

- **humanevalfix_t1fmt** (164 items): the T1 repair prompt. It shows the buggy function, the `check` test wrapped as `test_check`, and the real pytest error of the buggy solution. The error was precomputed in the sandbox, in the same way as for the training data. The answer is the T1 diagnosis JSON plus the fixed function in a python block, scored by the HumanEvalPack tests.
- **bugdetect_t3fmt** (328 items): the T3 review prompt on the same buggy and correct functions as `bugdetect`. An answer counts as "has a bug" if it contains a finding with category `bug`.

Reference answers score 1.000 on both tasks ([harness validation](../harness_validation/README.md)).

## Results

Exact McNemar tests on paired items.

### Within format: base vs adapter

| Task | n | Base | Adapter | Δ | only base | only adapter | p |
|---|---|---|---|---|---|---|---|
| humanevalfix (original prompt, earlier runs) | 164 | 25.0 | 29.9 | +4.9 | 16 | 24 | 0.268 |
| humanevalfix_t1fmt | 164 | 9.1 | 17.7 | **+8.5** | 9 | 23 | **0.020** |
| bugdetect (original prompt, earlier runs) | 328 | 53.0 | 54.9 | +1.8 | 13 | 19 | 0.377 |
| bugdetect_t3fmt (accuracy) | 328 | 49.7 | 60.4 | **+10.7** | 52 | 87 | **0.004** |

### Across formats: same model, same items

| Model | Pairing | Original | Trained format | Δ | p |
|---|---|---|---|---|---|
| Base | humanevalfix → t1fmt | 25.0 | 9.1 | −15.9 | 6.9e-5 |
| Adapter | humanevalfix → t1fmt | 29.9 | 17.7 | −12.2 | 0.002 |
| Base | bugdetect → t3fmt | 53.0 | 49.7 | −3.4 | 0.47 |
| Adapter | bugdetect → t3fmt | 54.9 | 60.4 | +5.5 | 0.24 |

### Formatting failures vs wrong fixes (repair)

The strict score needs the fix in a python block. A lenient re-extraction ignores fences and the JSON diagnosis (`lenient_code`, `experiments/scripts/lenient_fix_rescore.py`). It is applied to all four runs, and is analysis only.

| Run | Strict | Lenient |
|---|---|---|
| Base, original prompt | 25.0 | 25.0 |
| Adapter, original prompt | 29.9 | 29.9 |
| Base, T1 format | 9.1 | 18.9 |
| Adapter, T1 format | 17.7 | 17.7 |

### Repair by bug type (passed items, strict; base T1 format also lenient)

| Bug type | n | Base orig | Adapter orig | Base T1 (lenient) | Adapter T1 |
|---|---|---|---|---|---|
| operator misuse | 25 | 5 | **13** | 6 (8) | 9 |
| value misuse | 44 | 13 | 16 | 3 (7) | 14 |
| function misuse | 8 | 4 | 4 | 0 (2) | 3 |
| variable misuse | 23 | 9 | 5 | 2 (5) | **1** |
| missing logic | 33 | 4 | 4 | 2 (5) | **1** |
| excess logic | 31 | 6 | 7 | 2 (4) | **1** |

### Detection by bug type (correct verdicts)

| Items | n | Base orig | Adapter orig | Base T3 | Adapter T3 |
|---|---|---|---|---|---|
| correct code (specificity) | 164 | 29 | 27 | 105 | **139** |
| operator misuse | 25 | 23 | 25 | 13 | 13 |
| value misuse | 44 | 38 | 41 | 9 | **19** |
| function misuse | 8 | 7 | 7 | 1 | 1 |
| variable misuse | 23 | 21 | 22 | 10 | 6 |
| missing logic | 33 | 28 | 28 | 13 | **4** |
| excess logic | 31 | 28 | 30 | 12 | 16 |

## Interpretation

1. **The trained format does not unlock HumanEvalFix.** The adapter formats its answers almost perfectly (lenient = strict), yet it scores 12 points *lower* in its own format than with the original prompt. Format is therefore not the bottleneck. Why the T1 format is harder for both models was not isolated. Candidates: the answer must start with a diagnosis, and the prompt frames the task differently (imports shown, test wrapped for pytest, an error message added).
2. **Gains follow the bug types the training faults resemble.** The v1 operators are comparison and arithmetic swaps, off-by-one constants, boolean swaps and negated conditions. With the original prompt the adapter's repair gain sits in operator misuse (5 → 13). In the T1 format it keeps operator and value misuse but collapses on variable misuse, missing logic and excess logic (1 each). In detection, recall rises on value misuse and falls on missing logic. It has learned "find the one wrong token", and it applies that even where the bug is a missing statement.
3. **Over-reporting on human-written correct code is low.** In the T3 format the adapter flags only 25 of 164 correct functions (15 %). The 40.6 % false-bug rate in the internal evaluation comes from near-identical clean twins of buggy functions, a much harder contrast.
4. **The original detection prompt elicits a yes-bias.** With it, both models answer "has a bug" about 85 % of the time. The 53–55 % "accuracy" there is close to the 50 % base rate.

## Consequences for data v2

- **More bug types (main change).** Five new single-line operators that resemble human bug classes: `variable_misuse`, `missing_condition`, `missing_term`, `missing_call`, `function_swap` (`training/data/mutate.py`, family v2). Each new example is still kept only if a real test fails.
- **No prompt-variety augmentation.** The format check shows format is not what limits transfer.
- **A moderate number of verified clean reviews (500).** Over-reporting on real correct code is already low. Many more "no bug" targets could cost bug recall, which is the weak point on human-written bugs.
- **T4 execution traces** against the CRUXEval drop, as planned. That drop is independent of this check.

## Files

- `results/<task>/<run>/samples.jsonl`, `summary.json`: per-item answers and scores; `lenient.json` holds the lenient per-item outcomes for repair runs.
- `logs/`, `locali-evalgen.log`, `gpu_power.csv`: job logs and GPU power samples.
