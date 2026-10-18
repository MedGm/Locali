# Does a Python fine-tune help other languages? HumanEvalFix in five more languages

The fine-tune was trained on Python only. Here the same base and fine-tuned models
(Qwen2.5-Coder-1.5B-Instruct and the merged QLoRA v2 model) repair the 164 HumanEvalFix bugs in
JavaScript, Java, Go, C++ and Rust, with the same prompt as the Python task
(`evaluation/tasks/humanevalfix_multi.py`).

Runs on 2026-10-18, Kaggle (`training/kaggle/multilang`): vLLM 0.29.0, FP16, greedy, 768 new tokens,
the two models on separate T4s. The answers in this folder were generated once and never again;
they were scored three times as the harness was corrected (below), the last two times by
`locali-multilang-rescore` from these same saved answers. Table: `experiments/scripts/multilang_table.py
experiments/results/multilang_t4_rescore experiments/results/multilang_t4_rescore2`.

| Language | Problems scored | Base | Fine-tuned | Change | Only base fixed / only fine-tuned fixed | p (exact McNemar) |
|---|---|---|---|---|---|---|
| Python (for reference, [finetune_v2](../finetune_v2/README.md)) | 164 | 25.0 | 36.0 | +11.0 | | 0.006 |
| JavaScript | 164 of 164 | 22.6 | 32.3 | +9.8 | 5 / 21 | 0.0025 |
| Java | 164 of 164 | 38.4 | 31.7 | −6.7 | 24 / 13 | 0.099 |
| Go | 160 of 164 | 23.8 | 31.9 | +8.1 | 11 / 24 | 0.041 |
| C++ | 163 of 164 | 30.1 | 29.4 | −0.6 | 20 / 19 | 1 |
| Rust | 162 of 164 | 19.1 | 22.2 | +3.1 | 12 / 17 | 0.46 |

## What it says

- **The repair skill learned on Python partly carries over.** JavaScript (+9.8, p = 0.0025) and Go
  (+8.1, p = 0.041) improve about as much as Python did (+11.0). Rust moves the same way without
  significance.
- **Nothing is significantly worse**, but Java goes the other way (−6.7, p = 0.10) and C++ does not
  move. In the 24 Java problems the fine-tune lost, its answers have the same form and length as the
  base model's and fail the tests at run time: worse fixes, not a format problem. One run each, so
  this stays a trend.
- For the platform: the full assistant stays Python-only (its tests, repair loop and validation are
  Python), but the model the playground uses for other languages is not worse than the base model
  there, and better in two of five.

## How the harness was checked

Each language's program is assembled from the answer and the problem's test, then compiled and run
with that language's toolchain on the Kaggle VM. Before scoring, every problem's **reference
solution must pass and its buggy version must fail**; a problem whose reference fails is left out
for both models. Final check: reference solutions pass 164 / 164 / 160 / 163 / 162 (JS, Java, Go,
C++, Rust), buggy versions pass 0 everywhere. The left-out problems: Go/10, Go/32, Go/38, Go/50
(helpers or imports that exist only in the prompt), CPP/38 (its declaration already holds part of
the body), Rust/32 and Rust/50.

Three corrections were needed, each found by looking at why answers failed, not at the scores:

1. **Go imports.** Go rejects unused, missing or repeated imports, and the problems' own import
   lists did not always match their code (12 reference solutions failed). The harness now drops
   every import line and writes one block with exactly the packages the file uses (152 → 160
   references pass).
2. **Rust `use` lines** were added twice; every program failed to compile (0 → 162).
3. **Echoed test code.** The base model often repeats the test in its answer: Go `Test` functions
   (it scored 1 of 164 before this was fixed, then 39), the JS test function (19 answers), the C++
   helper `issame` (about 30 answers). Repeated test code is now removed before the real test is
   added, in every language, so an answer is judged on its fix. The fine-tuned model echoes much
   less, which is why fixing this mattered: it would have overstated the fine-tune by about 47 Go
   problems.

**This is the only experiment that ran model-written code outside the laptop's Docker sandbox.**
The toolchains for five languages did not fit the laptop's disk, so the answers were compiled and
run on the disposable Kaggle VM, which holds no secrets, with a timeout per program.

## Limits

One greedy answer per problem, so differences of a few problems are noise (the p-values say how
much). The prompt is the Python task's prompt with another code fence, not a prompt tuned per
language.
