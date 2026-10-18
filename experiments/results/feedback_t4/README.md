# Repair with execution feedback (HumanEvalFix, Python)

The benchmark gives a model one answer. Locali's repair agent instead runs the failing test after
each attempt and, when it still fails, asks again with the latest code and the error, up to three
times (`evaluation/feedback_repair.py`). This measures that setting, for the base model and the
fine-tune (QLoRA v2, merged), on the same 164 problems.

Run on 2026-10-18 in a Kaggle notebook with 2 x T4 (`training/kaggle/feedback`), vLLM 0.29.0, FP16,
first attempts greedy. Model-written code ran on the VM through `evaluation/isolated.py`: own empty
folder, clean environment, memory/CPU/process limits, 30 s timeout, and sockets disabled by a guard
(Kaggle's container does not allow network namespaces). Harness check first: all 164 reference
solutions pass and all 164 buggy versions fail, with the original tests and with the explained ones.

- **plain**: the error as the test gives it (mostly a bare `AssertionError`), greedy retries
- **explained**: failing assertions say what the code returned and what was expected, e.g.
  `has_close_elements([1.0, 2.0, 3.9, 4.0, 5.0, 2.2], 0.05) returned True, expected False` (they pass
  exactly when the original assertions do), and attempts 2 and 3 are sampled at temperature 0.6

| % fixed (of 164) | 1 attempt | within 2 | within 3 |
|---|---|---|---|
| Fine-tuned, plain | 36.0 | 39.6 | 39.6 |
| Fine-tuned, explained | 36.0 | 40.9 | **41.5** |
| Base, plain | 25.0 | 28.7 | 28.7 |
| Base, explained | 25.0 | 29.3 | 29.9 |

The first attempts reproduce the benchmark scores exactly (36.0 and 25.0).

Paired exact McNemar tests on the same problems:

| Comparison | Fixed | Only the first / only the second | p |
|---|---|---|---|
| Fine-tuned, 1 attempt vs 3 (plain) | 59 vs 65 | 0 / 6 | 0.031 |
| Fine-tuned, 1 attempt vs 3 (explained) | 59 vs 68 | 0 / 9 | 0.004 |
| Fine-tuned, plain vs explained (3 attempts) | 65 vs 68 | 2 / 5 | 0.45 |
| Base, 1 attempt vs 3 (plain) | 41 vs 47 | 0 / 6 | 0.031 |
| Base, 1 attempt vs 3 (explained) | 41 vs 49 | 0 / 8 | 0.008 |
| Base, plain vs explained (3 attempts) | 47 vs 49 | 2 / 4 | 0.69 |
| Explained, 3 attempts: base vs fine-tuned | 49 vs 68 | 13 / 32 | 0.007 |
| Base with 3 attempts vs fine-tuned with 1 | 49 vs 59 | 14 / 24 | 0.14 |

## What it says

- **Feedback helps both models, by about the same amount** (+6 to +9 problems), and never costs a
  problem: no problem was fixed at the first attempt and lost later, since a passing fix ends the loop.
- **Saying what the code returned, and sampling the retries, adds a little more** (+3 fine-tuned,
  +2 base), not significant on its own.
- **The fine-tune keeps its lead with feedback** (41.5 vs 29.9, p = 0.007), and in one attempt it
  fixes more than the base model does in three (36.0 vs 29.9, a trend, p = 0.14).
- The gain is small because the model rarely uses the error. In the laptop run of the deployed Q8
  model (`../feedback_repair/ft-q8/`: 31.7 → 34.8 with plain feedback), 49 of the 66 problems it never
  fixed got an identical second answer. Training on its own failed attempts is the obvious next
  step (`docs/v3-plan.md`).

## Limits

The tests shown in the prompt are the tests that decide the score, as when the agent repairs code
against a failing test; this is not unaided repair. One run per setting. The retries in the
explained setting are sampled, so they depend on the seed (3407).
