# Fine-tuning mixture v2

Built 2026-10-13 with `training/data/build_mix.py` at commit `371ff29`. Published as the private Kaggle dataset `locali-mix-v2`. It is a **strict superset of v1**: all 11,516 v1 rows are present byte-identical and in the same split (checked by id, messages and split). Rebuilding v1 with the current code also reproduces `mix_v1` byte for byte.

```
uv run python -m training.data.build_mix \
  --t1 data/t1/mutation_v1.notimeout.clean.jsonl data/t1/mutation_v2ops.notimeout.clean.jsonl \
  --t3-pairs 1000 339 --t3-verified-clean 500 \
  --t2 data/t2/tests_v1.clean.jsonl --t4 data/t4/trace_v1.jsonl \
  --explanations data/teacher/explanations.jsonl data/teacher_v2/explanations.jsonl --out data/mix_v2
```

## Why these additions

The changes follow from the QLoRA v1 results ([format-transfer check](../format_transfer_qwen25_v1/README.md), [benchmarks](../finetune_qwen25_qlora_v1/README.md)):

| Observation (v1) | Addition |
|---|---|
| CRUXEval-O fell 30.1 → 25.5 (p = 0.0005) | **T4 execution traces** |
| HumanEvalFix gains only on bug types like the v1 faults; variable misuse and missing/excess logic collapse in the T1 format | **v2 mutation operators** for T1 and T3 |
| 40.6 % false bug reports on clean twins in the internal evaluation (but only 15 % on HumanEvalPack correct code) | **500 verified clean reviews** (moderate, to protect recall) |
| The trained prompt format does not unlock the benchmark | no prompt-variety augmentation |

## New components

**T4: execution trace** (`training/data/t4_trace.py`, `build_t4.py`). 2,400 CodeRM-UnitTest problems were sampled (seed 23). Calls come from each problem's own unittest suite: literal assignments in the test method are inlined, so arguments are literals, and `result = f(x)` / `assertEqual(result, expected)` chains are resolved. Each call is executed in the sandbox. It is kept only if the traced `repr` is a literal **equal (same type) to the literal the test expects**, so two independent sources agree on every label. Floats with long expansions and outputs over 120 characters are dropped. One call per problem gives 1,952 examples. Decontamination dropped 18 (HumanEval+ 5, HumanEvalPack 5, MBPP+ 8). Output types: int 1,027, list 438, str 390, tuple 81, other 16. The prompt is our own wording, answered with `assert <call> == <value>`, and is not the CRUXEval template. A CRUXEval gain therefore reflects the skill, not a memorised prompt.

**T1 with v2 operators** (`training/data/mutate.py` family v2). The operators are `variable_misuse`, `missing_condition`, `missing_term`, `missing_call` and `function_swap`. As in v1, each is a single-line in-place edit, and a mutant is kept only if a real test fails. 1,500 problems were sampled (seed 29) and operators are tried round-robin, which gave 2,888 mutants. A cap of 500 per operator kept 1,413. Dropping timeouts left 1,394, and 13-gram decontamination left **1,381**:

| Operator | variable_misuse | missing_term | function_swap | missing_call | missing_condition |
|---|---|---|---|---|---|
| Examples | 493 | 485 | 141 | 141 | 121 |

Explanations come from Qwen3.5-9B: a Kaggle job with 2×T4 and TP = 2, 50 min of wall time, and 118k output tokens. 1,325 / 1,381 (96 %) passed the acceptance check; the rest use the template. As in v1, a quarter of the groups (339 examples) become T3 bug/clean pairs instead of T1.

**Verified clean reviews.** The test-verified original of the first 500 non-reserved T1 groups is shown alone as a T3 item. Its answer contains only tool findings and no bug.

## Counts

| Split | T1 | T2 | T3 | T4 | replay | total |
|---|---|---|---|---|---|---|
| train | 4,323 | 2,619 | 3,641 | 1,775 | 1,794 | 14,152 |
| val | 252 | 148 | 185 | 81 | 86 | 752 |
| test | 212 | 134 | 229 | 96 | 113 | 784 |

The T3 set has 4,055 items: 1,339 with a bug finding and 1,859 with no finding at all. In v1 it was 2,877 items, 1,000 with a bug finding. Groups in more than one split: **0**. Training rows grow by 36 % over v1 (10,385 → 14,152).

## Files

`stats.json` (mixture), `t4_trace_v1.stats.json`, `t1_v2ops.stats.json` (builders).
