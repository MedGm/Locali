# v3 fine-tune: plan

Status: proposal, 2026-10-18. Goal: better repair, in Python and in other languages, measured on the
same benchmarks with the same paired tests as v2.

## Why v2 is limited

- **Its bugs are not real bugs.** v2 repair data comes from single-line mutations (`<` → `<=`,
  `-` → `+`). The model fixes 64 % of held-out bugs of that kind but 36 % of HumanEvalFix, whose bugs
  are written by people: several lines, missing cases, wrong logic.
- **Its fixes are minimal edits**, so it learned to patch a line, not to rethink a function.
- **It was trained on Python only**, and it is level or worse in C++, Rust and Java.
- **It cannot use feedback.** With the test error and two more tries it went from 31.7 % to 34.8 %;
  in 49 of 66 failures its second answer was identical to its first. It has never seen an example
  of "your fix failed, here is why, fix it properly".

## Data

### 1. Problems in six languages

- Python: CodeRM-UnitTest problems (solution + unit tests), as in v1/v2.
- JavaScript, Java, Go, C++, Rust: a teacher model translates a sample of those Python problems,
  solution and tests together. A translation is kept only if its translated tests pass on its
  translated solution, run with the language's toolchain (the five-language harness,
  `evaluation/tasks/humanevalfix_multi.py`). This is how MultiPL-T builds data for languages with
  little training code.
- Teacher: Qwen2.5-Coder-7B-Instruct (Apache-2.0), served with vLLM on both T4s. The v2 teacher
  (Qwen3.5-9B) is the fallback.

### 2. Realistic bugs

- The teacher gets a correct solution and is asked for one bug a developer would plausibly make,
  from a list of kinds (wrong condition, off-by-one, missing case, wrong variable, wrong
  accumulation, early return, several lines), spread evenly.
- A bug is kept only if at least one test fails on it, it changes behaviour, not just names, and it
  is not identical to another bug of the same problem.
- The v2 mutation bugs stay as a share of the mix, so what v2 does well is not lost.

### 3. Targets

- The fix is the **whole correct function**, verified by the tests, not the smallest edit.
- A one-to-two-sentence diagnosis by the teacher, kept only if it names the changed lines (the v2
  consistency check).
- Formats: the trained repair format (T1), the benchmark-style "Fix bugs in X", and a new retry
  format (below).

### 4. Self-correction, by rejection sampling

- The v2 model attempts every training bug several times (temperature 0.8) with execution feedback,
  using the improved errors ("returned X, expected Y").
- Every attempt is run. A failed attempt and its error become the input of a **retry example**,
  and the target is a fix that passes (the model's own later attempt, else the reference).
- Attempts that pass first time are kept as extra correct targets (the STaR method: train on your
  own verified successes).
- This is the part aimed at the feedback result: the model learns what to do with an error.

### 5. Keeping the benchmarks out

- 13-gram decontamination against HumanEvalPack in all six languages, HumanEval+, MBPP+,
  CRUXEval and the security sets, as in v2.
- Problems whose function name or signature matches a HumanEval entry point are dropped as well,
  since translated problems could collide with HumanEvalPack's own translations.

### 6. Mix

About 6k Python repair + 6k repair in the five other languages + 3k retry examples, plus the v2
tests, review and trace data as replay, so those skills are not forgotten. Final counts depend on
what survives verification.

## Training and evaluation

- QLoRA with the v2 recipe (rank 16, all projections, 2 epochs, one T4), so the data is the only
  change.
- Evaluated like v2: all ten benchmarks, HumanEvalFix in the five other languages, and repair with
  feedback (plain and improved). Paired exact McNemar tests against v2 and against the base.
- **Final comparison** against a larger base model, Qwen2.5-Coder-7B-Instruct, on the same tasks,
  with one attempt and with feedback, to show what the 1.5B model gains and what remains.

## Where it runs

All of it on Kaggle: translation and bug generation (teacher on 2 T4s), rejection sampling,
fine-tuning and evaluation, with model and teacher code run by the isolated runner
(`evaluation/isolated.py`). The laptop is used only for a final check of the deployed Q8 model.

## Risks

- Translations of poor quality: kept only when their own tests pass, and a sample is read by hand.
- A teacher bug that is not realistic: the kinds are fixed in advance, and a sample is read by hand.
- Gains that do not transfer to HumanEvalFix: measured, and reported either way.
