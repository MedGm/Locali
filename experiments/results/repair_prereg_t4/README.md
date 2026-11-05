# Repair on real bugs (pre-registered check, part 1)

Protocol: `docs/preregistration-repair.md`, registered in commit 15aa6b9 (2026-11-05 14:56)
before any model answered these programs. Benchmarks, after the harness check:
`../condefects` (382 ConDefects programs, contests from 2024-02-01, 129 tasks) and `../quixbugs`
(40 programs). Job: `training/kaggle/repair_prereg`, Kaggle 2 x T4, vLLM 0.29 with the
generation_config defaults, greedy, at most 1,024 output tokens, the registered prompt. Scored in
the local Docker sandbox by `experiments/scripts/repair_prereg.py` (10 s per test, a program is
fixed when every test passes), which also prints the tables below.

## Result

| Comparison | n | base fixed | fine-tune fixed | only base / only fine-tune | difference, points (95 % CI) | p | Holm p |
|---|---|---|---|---|---|---|---|
| **Primary: ConDefects, run D vs 3B base** | 382 | 47 | 57 | 24 / 34 | +2.6 (−1.3 to +6.5) | **0.24** | (one test) |
| ConDefects: run E vs 3B base | 382 | 47 | 56 | 25 / 34 | +2.4 (−1.6 to +6.3) | 0.30 | 0.79 |
| ConDefects: run C vs 3B base | 382 | 47 | 58 | 23 / 34 | +2.9 (−1.0 to +6.7) | 0.18 | 0.74 |
| ConDefects: 1.5B QLoRA v2 vs 1.5B base | 382 | 29 | 23 | 13 / 7 | −1.6 (−3.9 to +0.7) | 0.26 | 0.79 |
| QuixBugs: run D vs 3B base | 40 | 20 | 29 | 2 / 11 | +22.5 (+6.3 to +38.7) | 0.022 | 0.16 |
| QuixBugs: run E vs 3B base | 40 | 20 | 28 | 4 / 12 | +20.0 (+1.4 to +38.6) | 0.077 | 0.38 |
| QuixBugs: run C vs 3B base | 40 | 20 | 28 | 2 / 10 | +20.0 (+4.2 to +35.8) | 0.039 | 0.23 |
| QuixBugs: 1.5B QLoRA v2 vs 1.5B base | 40 | 13 | 12 | 3 / 2 | −2.5 (−13.4 to +8.4) | 1.0 | 1.0 |

The secondary rows are Holm-corrected together. The interval is a Wald interval for a paired
difference of proportions.

Also reported, not used for the decision: one program per task (the lowest submission id), run D
vs base: 17 vs 13 of 129, 10 / 6 discordant, p = 0.45.

| Model | ConDefects fixed (of 382) | cut off at 1,024 tokens | QuixBugs fixed (of 40) |
|---|---|---|---|
| 3B base | 47 | 22 | 20 |
| Run C | 58 | 18 | 28 |
| Run D | 57 | 18 | 29 |
| Run E | 56 | 18 | 28 |
| 1.5B base | 29 | 19 | 13 |
| 1.5B QLoRA v2 | 23 | 19 | 12 |

## Outcome, as registered

**D better, p ≥ 0.05.** The registered sentence:

> On real bugs outside the training distribution, the repair gain is not confirmed: +2.6 points
> (95 % CI −1.3 to +6.5), p = 0.24.

The HumanEvalFix gain (46 → 62 %) is therefore described as mostly within the training
distribution.

## Reading

- All three 3B runs fix slightly more real bugs than the base (+2.4 to +2.9 points), but the
  interval includes zero: a gain of a few points is possible, the 15 points of HumanEvalFix are not.
- These bugs are hard for every model: the best fixes 15 % of them. ConDefects programs are
  whole contest solutions (median about 700 characters of prompt, up to 27,000), with only a
  failing input and output to go on, no description of the problem.
- On QuixBugs the 3B runs gain about 20 points (D: p = 0.022 before correction, 0.16 after). It is
  a secondary benchmark with 40 programs, public since 2017 and very likely seen in training, as
  registered; it does not change the outcome.
- The 1.5B fine-tune is not better than its base on either benchmark.

## Deviations from the protocol, all before scoring

- The first full Kaggle run stopped after about 60 programs per model: five ConDefects prompts are
  longer than the 8,192-token window the vLLM servers were started with (some contestants paste a
  whole library into every submission). The servers were restarted with a 16,384-token window; the
  prompt and the 1,024-token answer limit are unchanged. The partial answers of that run are kept
  in `../repair_prereg_t4_attempt1`.
- Tests run smallest input first and stop at the first failure (decided during the harness check,
  before any model answer): the outcome is the same, since a program is fixed only when every test
  passes.
- Output comparison strips trailing whitespace, as registered; ConDefects' own tool compares lines
  exactly. The same rule applies to every model and to the harness check.

## Found after scoring (2026-11-06), not yet applied to the tables above

The 3B base sometimes puts its whole answer in a block labelled `markdown` (the registered prompt
asks for "a markdown code block"), and the code extraction skipped such blocks. It is fixed in
`evaluation/extract.py` (a `markdown` block that is valid Python counts as code); the fine-tuned
models never answer this way, so only the base can change.

- QuixBugs, 3B base: rescored, 20 → 21 of 40 (one such answer was a correct fix).
- ConDefects, 3B base: 31 answers are written this way, all scored as failures. The test files
  are on an external drive that is not connected, so they are not rescored yet. Run on the one
  failing input shown in the prompt, 22 of the 31 still fail it, so at most 9 can be fixes: the
  base reaches at most 56 of 382, below run D's 57, and the registered outcome ("D better,
  p ≥ 0.05", gain not confirmed) cannot change. The numbers in the registered sentence will be
  updated, with the original ones kept, once the 31 are rescored.

## Files

- `results/<benchmark>/<model>/`: `samples.jsonl` (answers and scores; `samples.original.jsonl`
  before scoring), `summary.json`.
- `logs/`, `*.log`, `kaggle_repair_prereg.py`: the Kaggle job and its logs.

Code and text written with AI help (Claude); every figure above comes from the files listed here.
