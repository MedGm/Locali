# Pre-registered checks of the two main claims: repair and test generation

Written before any model answer on these benchmarks was generated or looked at. The commit that adds
this file is the registration; every run records the commit it ran at, which must be this one or a
later one that changes only code, not this protocol.

## Why

The repair gain of the fine-tuned 3B (HumanEvalFix 46 → 62 %) has two weaknesses:

1. the seven kinds of realistic bugs in the v3 training data were chosen after reading HumanEvalFix's
   per-type results, and two of them carry its category names (missing logic, excess logic), so
   the gain may partly come from training on the benchmark's bug distribution;
2. runs A to E were compared, and C then D chosen, on the same benchmarks the gain is reported on.

This evaluation uses real bugs that no part of the project has looked at, with the analysis fixed in
advance. A second check, on test generation, is at the end (part 2).

# Part 1: repair on real bugs

## Benchmarks

**Primary: ConDefects, Python** (Wu et al., 2023; github.com/appmlk/ConDefects, data CC BY-SA 4.0).
Wrong submissions people made on AtCoder, each with the same person's later accepted submission and
AtCoder's test cases.

- Tasks whose contest started on or after **2024-02-01**: Qwen2.5-Coder's report says its GitHub
  data covers repositories created before February 2024. Its web data has no stated date, and the
  model was released in September 2024, so these bugs could still have been on the web at training
  time. Contamination affects base and fine-tune alike (the comparison is paired).
- That is 489 faulty programs in 161 tasks (counted from `date.txt` and `Code/` at commit
  43f0834a82c5, before downloading any test).
- Harness check, before any model runs: a program is kept only if its accepted version passes all
  of its tests and its faulty version fails at least one, in the Docker sandbox with the timeout
  below. Problems with several accepted outputs (special judges) drop out here, since the check
  compares output exactly. The kept count is recorded before generation starts.

**Secondary: QuixBugs, Python** (Lin et al., 2017), 40 programs with one-line bugs and their tests.
Public since 2017 and very likely seen in training by both models. It cannot settle the question:
with 40 programs, a real gain can easily fail to reach significance.

**Not used: DebugBench.** Answers are judged by LeetCode's online judge on hidden tests; scoring
locally would need tests written by me, which is the kind of design choice this evaluation avoids.

## Prompt

The models were trained on "code + failing test + error". ConDefects programs read standard input
and have no problem statement in the dataset, so the prompt shows the program and one failing test
as input / expected output / actual output:

```
Fix the bug in this program. It reads from standard input and writes to standard output.

```python
<faulty program>
```

This test fails.
Input:
<input>
Expected output:
<expected>
Actual output:
<actual output, or the last line of the error, or "time limit exceeded">

Return the complete fixed program in a markdown code block.
```

- The failing test shown is the one with the smallest input file (ties: by file name). Input,
  expected and actual output are cut at 1,000 characters each, with "[...]" appended when cut.
- QuixBugs: the function, one failing test as a call with its expected and actual result, the same
  instruction for a function.
- This wording was fixed on three ConDefects programs dated before 2023-01-01, which are not part
  of the evaluation, by checking only that the prompt is well formed and that the answer can be
  extracted; no scores were computed on them. It is not changed after any evaluation answer is
  seen. Base and fine-tuned models get the same prompt.

## Generation and scoring

- Kaggle T4, vLLM 0.29 with the models' generation_config defaults (as in all other Kaggle runs),
  greedy, at most 1,024 output tokens, one answer per program.
- Extraction: the Python code block of the answer, as for HumanEvalFix (`evaluation/extract.py`).
- Scoring in the local Docker sandbox: the fixed program runs on every test of its task, 10 s per
  test (the same limit for every model and for the harness check). Output is compared line by line
  after stripping trailing whitespace, as in ConDefects' own tool. A program is fixed when every
  test passes. A timeout or crash on any test is a failure.

## Models and comparisons

- **Primary:** Qwen2.5-Coder-3B-Instruct (base) vs **run D** (the deployed model), same base
  revision as in all 3B runs.
- **Secondary:** run E vs base, run C vs base; Qwen2.5-Coder-1.5B-Instruct vs the 1.5B QLoRA v2.

## Analysis

- Test: exact McNemar on the paired outcomes (fixed / not fixed per program).
- **Primary hypothesis:** on ConDefects (post-2024-02-01), run D fixes more programs than the base,
  exact McNemar p < 0.05. There is one primary comparison, so no correction applies to it.
- **Secondary:** the other model comparisons on ConDefects, and every comparison on QuixBugs,
  Holm-corrected together, reported as secondary.
- A task can have several faulty programs (489 in 161 tasks), so outcomes are not fully
  independent. Also reported, not used for the decision: the same test with one program per task
  (the lowest submission id).
- Reported for every comparison: fixed counts, discordant pairs, the difference in percentage
  points with a 95 % confidence interval.

## What gets written for each outcome

- **D better, p < 0.05:** "The repair gain holds on real bugs from after the base model's GitHub
  data cutoff (ConDefects): +x points, p = y." The headline keeps the repair result, with this
  number next to the HumanEvalFix one.
- **D better, p ≥ 0.05:** "On real bugs outside the training distribution, the repair gain is not
  confirmed: +x points (95 % CI a to b), p = y." The HumanEvalFix gain is then described as mostly
  within the training distribution. No "partly holds".
- **D not better:** "The repair gain does not carry over to real bugs outside the training
  distribution." The HumanEvalFix gain is described as within the training distribution.

# Part 2: test generation with a larger token budget

## Why

Every model had at most 768 output tokens. On test generation (HumanEvalPack, 164 problems) the 3B
base hit that limit on 100 answers (mean 579 tokens) and run D on 1 (mean 111). The base kept no
test on 55 problems, 41 of them cut off; run D on 5. Among the problems where the base kept a
suite, it caught the bug in 94 % (102 / 109), run D in 86 % (136 / 159). So a large part of the
reported gain (62 → 83 % of bugs caught) may come from the budget, not from better tests. These
numbers were looked at before this part was written; the rerun below has not been run.

## Run

- Task `testgen` exactly as before (prompt, scoring, 60 s per suite on the correct and on the buggy
  code), with **2,048 output tokens** instead of 768. The scoring also records, from this version
  on, whether a catch was a timeout and how long the suite took on the correct code.
- Models: the 3B base and run D (primary), run E, the 1.5B base and the 1.5B QLoRA v2 (secondary).
  Kaggle T4, vLLM 0.29 with the generation_config defaults, greedy, as before.
- Scored in the local Docker sandbox.

## Analysis

- **Primary hypothesis:** at 2,048 tokens, run D catches more bugs than the base, exact McNemar
  p < 0.05. One primary comparison, no correction.
- **Secondary:** run E vs base and 1.5B QLoRA v2 vs 1.5B base, Holm-corrected together.
- Reported for every model: truncated answers, problems with a non-empty kept suite, bugs caught,
  the catch rate among problems with a non-empty suite, catches that were timeouts.

## What gets written for each outcome

- **D better, p < 0.05:** "With a budget large enough for the base, the fine-tune still catches
  more bugs: x vs y of 164, p = z." The 768-token numbers stay, with the truncation counts next to
  them.
- **D better, p ≥ 0.05, or not better:** "The test-generation gain at 768 tokens was mostly the base
  running out of tokens; with 2,048 tokens it is x vs y, p = z (not significant)." The headline
  drops the test-generation gain; what remains is that the fine-tune writes shorter test files.
