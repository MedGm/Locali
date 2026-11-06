# Repair on real bugs (pre-registered check, part 1)

Protocol: `docs/preregistration-repair.md`, registered in commit 15aa6b9 (2026-11-05 14:56)
before any model answered these programs. Benchmarks, after the harness check:
`../condefects` (382 ConDefects programs, contests from 2024-02-01, 129 tasks) and `../quixbugs`
(40 programs). Job: `training/kaggle/evaluate/repair_prereg`, Kaggle 2 x T4, vLLM 0.29 with the
generation_config defaults, greedy, at most 1,024 output tokens, the registered prompt. Scored in
the local Docker sandbox by `experiments/scripts/stats/repair_prereg.py` (10 s per test, a program is
fixed when every test passes), which also prints the tables below.

## Result

Scored with the corrected code extraction (see "Found after scoring" below); the numbers as first
scored are kept in that section.

| Comparison | n | base fixed | fine-tune fixed | only base / only fine-tune | difference, points (95 % CI) | p | Holm p |
|---|---|---|---|---|---|---|---|
| **Primary: ConDefects, run D vs 3B base** | 382 | 54 | 57 | 28 / 31 | +0.8 (-3.2 to +4.7) | **0.79** | (one test) |
| ConDefects: run E vs 3B base | 382 | 54 | 56 | 28 / 30 | +0.5 (-3.4 to +4.4) | 0.9 | 1 |
| ConDefects: run C vs 3B base | 382 | 54 | 58 | 26 / 30 | +1.0 (-2.8 to +4.9) | 0.69 | 1 |
| ConDefects: 1.5B QLoRA v2 vs 1.5B base | 382 | 29 | 23 | 13 / 7 | -1.6 (-3.9 to +0.7) | 0.26 | 1 |
| QuixBugs: run D vs 3B base | 40 | 21 | 29 | 3 / 11 | +20.0 (+2.7 to +37.3) | 0.057 | 0.4 |
| QuixBugs: run E vs 3B base | 40 | 21 | 28 | 4 / 11 | +17.5 (-0.7 to +35.7) | 0.12 | 0.59 |
| QuixBugs: run C vs 3B base | 40 | 21 | 28 | 3 / 10 | +17.5 (+0.7 to +34.3) | 0.092 | 0.55 |
| QuixBugs: 1.5B QLoRA v2 vs 1.5B base | 40 | 13 | 12 | 3 / 2 | -2.5 (-13.4 to +8.4) | 1 | 1 |

The secondary rows are Holm-corrected together. The interval is a Wald interval for a paired
difference of proportions.

Also reported, not used for the decision: one program per task (the lowest submission id), run D
vs base: 17 vs 13 of 129, 6 / 10 discordant, p = 0.45.

| Model | ConDefects fixed (of 382) | cut off at 1,024 tokens | QuixBugs fixed (of 40) |
|---|---|---|---|
| 3B base | 54 | 22 | 21 |
| run D | 57 | 18 | 29 |
| run E | 56 | 18 | 28 |
| run C | 58 | 18 | 28 |
| 1.5B base | 29 | 19 | 13 |
| 1.5B QLoRA v2 | 23 | 19 | 12 |

## Outcome, as registered

**D better, p ≥ 0.05.** The registered sentence:

> On real bugs outside the training distribution, the repair gain is not confirmed: +0.8 points
> (95 % CI −3.2 to +4.7), p = 0.79.

As first scored (before the extraction fix): +2.6 points (95 % CI −1.3 to +6.5), p = 0.24; the same
outcome.

The HumanEvalFix gain (50 → 62 %) is therefore described as mostly within the training
distribution.

## Reading

- All three 3B runs fix about as many real bugs as the base (+0.5 to +1.0 points); the interval
  includes zero: a gain of a few points is possible, the 12 points of HumanEvalFix are not.
- These bugs are hard for every model: the best fixes 15 % of them. ConDefects programs are
  whole contest solutions (median about 700 characters of prompt, up to 27,000), with only a
  failing input and output to go on, no description of the problem.
- On QuixBugs the 3B runs gain 17.5 to 20 points (D: p = 0.057 before correction, 0.40 after). It is
  a secondary benchmark with 40 programs, public since 2017 and very likely seen in training, as
  registered; it does not change the outcome.
- The 1.5B fine-tune is not better than its base on either benchmark.

## Deviations from the protocol, all before scoring

- The first full Kaggle run stopped after about 60 programs per model: five ConDefects prompts are
  longer than the 8,192-token window the vLLM servers were started with (some contestants paste a
  whole library into every submission). The servers were restarted with a 16,384-token window; the
  prompt and the 1,024-token answer limit are unchanged. The partial answers of that run are kept
  in `../../archive/repair_prereg_t4_attempt1`.
- Tests run smallest input first and stop at the first failure (decided during the harness check,
  before any model answer): the outcome is the same, since a program is fixed only when every test
  passes.
- Output comparison strips trailing whitespace, as registered; ConDefects' own tool compares lines
  exactly. The same rule applies to every model and to the harness check.

## Found after scoring (2026-11-06)

The 3B base sometimes puts its whole answer in a block labelled `markdown` (the registered prompt
asks for "a markdown code block"), and the code extraction skipped such blocks. It is fixed in
`evaluation/extract.py` (a `markdown` block that is valid Python counts as code). The fine-tuned
models never answer this way, so only the base changed; its answers were rescored, the first
scores are in `samples.original.jsonl` and `summary.json` (`rescored`).

| 3B base | As first scored | Rescored |
|---|---|---|
| ConDefects fixed (of 382) | 47 | **54** (7 of its 31 `markdown` answers are correct fixes) |
| QuixBugs fixed (of 40) | 20 | **21** |
| Run D vs base on ConDefects | +2.6 points, p = 0.24 | **+0.8 points, p = 0.79** |
| QuixBugs, run D vs base | p = 0.022, Holm 0.16 | p = 0.057, Holm 0.40 |

The registered outcome is the same under both: the gain is not confirmed.

## Files

- `results/<benchmark>/<model>/`: `samples.jsonl` (answers and scores; `samples.original.jsonl`
  before scoring), `summary.json`.
- `logs/`, `*.log`, `kaggle_repair_prereg.py`: the Kaggle job and its logs.

Code and text written with AI help (Claude); every figure above comes from the files listed here.
